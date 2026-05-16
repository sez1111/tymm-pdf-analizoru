
import re
from dataclasses import dataclass
from typing import List, Tuple, Dict
from collections import Counter
import streamlit as st
import fitz

APP_VERSION = "v8 - ANA SORU TEK YORUM / ALT MADDE DESTEKLİ SÜRÜM"


@dataclass
class Outcome:
    code: str
    grade: str
    theme: str
    text: str
    processes: List[str]
    evidences: List[str]


@dataclass
class Question:
    no: int
    text: str
    subparts: List[str]


def norm(t: str) -> str:
    return (t or "").lower().replace("ı", "i")


def has_any(t: str, words: List[str]) -> bool:
    nt = norm(t)
    return any(norm(w) in nt for w in words)


def grade_no(s: str) -> str:
    m = re.search(r"\d+", s or "")
    return m.group(0) if m else ""


def code_grade(code: str) -> str:
    m = re.search(r"BİY\.(\d+)\.|BIY\.(\d+)\.|Biy\.(\d+)\.", code or "")
    if not m:
        return ""
    return next(g for g in m.groups() if g)


def read_pdf(file) -> str:
    data = file.read()
    doc = fitz.open(stream=data, filetype="pdf")
    return "\n".join([p.get_text("text") for p in doc])


def is_real_question_marker(text: str, match: re.Match) -> bool:
    """
    Prevent false splits inside question body.
    A real question marker should usually be at line start and followed by meaningful question text.
    """
    idx = match.start()
    prefix = text[max(0, idx-40):idx]
    suffix = text[match.end():match.end()+120]

    # Must be start of line or after a clear newline.
    if idx > 0 and not text[idx-1] == "\n":
        return False

    # Avoid splitting point values like 1.5, dates, or list noise.
    if re.match(r"\s*\d", suffix):
        return False

    # Need enough alphabetic content after marker.
    letters = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]", suffix)
    if len(letters) < 8:
        return False

    return True


def detect_subparts(q_text: str) -> List[str]:
    """
    Detect a), b), c) or A), B) or a. b. style subparts.
    These are not treated as separate main questions.
    """
    parts = []
    # Normalize common subpart markers onto new lines for detection
    t = re.sub(r"\s+([a-eA-E])[\)\.]\s+", r"\n\1) ", q_text)
    matches = list(re.finditer(r"(?:^|\n)\s*([a-eA-E])[\)\.]\s+", t))
    if not matches:
        return []

    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i+1].start() if i+1 < len(matches) else len(t)
        body = t[start:end].strip()
        if body:
            parts.append(f"{m.group(1).lower()}) {body}")
    return parts


def split_questions(text: str) -> List[Question]:
    """
    Main-question splitter.
    - Splits only on real main question numbers: 1. 2. 3.
    - Keeps a), b), c) as subparts under the same main question.
    - Avoids duplicating Soru 1 if PDF text repeats headers or internal numbering.
    """
    t = text.replace("\r", "\n")
    # Put likely main question markers at line start, but don't touch decimals.
    t = re.sub(r"(?<![\d])\s+(\d{1,2})[\.\)]\s+(?=[A-Za-zÇĞİÖŞÜçğıöşü])", r"\n\1. ", t)

    all_matches = list(re.finditer(r"(?:^|\n)\s*(\d{1,2})[\.\)]\s+", t))
    matches = [m for m in all_matches if is_real_question_marker(t, m)]

    if not matches:
        return [Question(1, t.strip(), detect_subparts(t.strip()))] if t.strip() else []

    questions = []
    seen_positions = set()

    for i, m in enumerate(matches):
        q_no = int(m.group(1))
        start = m.end()
        end = matches[i+1].start() if i+1 < len(matches) else len(t)
        body = t[start:end].strip()

        # Basic cleanup for repeated page headers/footers
        body = re.sub(r"\n\s*\d+\s*$", "", body).strip()

        if body:
            # If same question number appears again due to PDF artifacts, merge into existing question
            existing = next((q for q in questions if q.no == q_no), None)
            if existing:
                existing.text += "\n" + body
                existing.subparts = detect_subparts(existing.text)
            else:
                questions.append(Question(q_no, body, detect_subparts(body)))

    # Sort by question number and drop exact duplicate texts
    unique = []
    seen = set()
    for q in sorted(questions, key=lambda x: x.no):
        key = (q.no, re.sub(r"\s+", " ", q.text[:200]))
        if key not in seen:
            unique.append(q)
            seen.add(key)
    return unique


def fallback_outcomes_for_grade(grade: str) -> List[Outcome]:
    if grade == "9":
        return [
            Outcome("BİY.9-YAŞAM", "9", "Yaşam", "Bilimsel araştırma, sınıflandırma ve biyoçeşitlilik konularını sorgulama/yorumlama.", ["sorgulama", "sınıflandırma", "yorumlama"], ["açık uçlu soru", "senaryo analizi"]),
            Outcome("BİY.9-ORGANİZASYON", "9", "Organizasyon", "Canlılarda organizasyon düzeyleri ve hücresel yapıları ilişkilendirme.", ["açıklama", "karşılaştırma", "ilişkilendirme"], ["açık uçlu soru", "şema", "model"]),
        ]
    if grade == "10":
        return [
            Outcome("BİY.10-ENERJİ", "10", "Enerji", "Canlılarda enerji dönüşümleri, solunum, fotosentez ve fermantasyon süreçlerini açıklama/karşılaştırma.", ["açıklama", "karşılaştırma", "çıkarım yapma", "gerekçelendirme"], ["açık uçlu soru", "tablo yorumlama", "bilgi kartı analizi"]),
            Outcome("BİY.10-EKOLOJİ-ENERJİ-AKIŞI", "10", "Ekoloji", "Ekosistemde enerji akışı, madde döngüleri, biyokütle ve süksesyon ilişkilerini yorumlama.", ["yorumlama", "neden-sonuç kurma", "çıkarım yapma", "değerlendirme"], ["grafik yorumlama", "açık uçlu soru", "senaryo analizi"]),
            Outcome("BİY.10-EKOLOJİ-CANLI-İLİŞKİLERİ", "10", "Ekoloji", "Canlılar arasındaki ekolojik ilişkileri, rekabeti, simbiyozu, popülasyon dinamiklerini ve besin ağlarını analiz etme.", ["sınıflandırma", "karşılaştırma", "gerekçelendirme", "analiz"], ["açık uçlu soru", "grafik çizme", "besin ağı oluşturma"]),
        ]
    if grade == "11":
        return [
            Outcome("BİY.11-TEPKİ", "11", "Tepki", "Canlılarda tepki, sinir sistemi, duyu organları ve hormonal düzenleme süreçlerini açıklama/yorumlama.", ["açıklama", "yorumlama", "karşılaştırma"], ["açık uçlu soru", "vaka analizi"]),
            Outcome("BİY.11-HOMEOSTAZİ", "11", "Homeostazi", "Homeostazi, dolaşım, solunum, boşaltım ve sindirim süreçlerini ilişkilendirme.", ["ilişkilendirme", "neden-sonuç kurma", "değerlendirme"], ["açık uçlu soru", "şema", "vaka analizi"]),
        ]
    if grade == "12":
        return [
            Outcome("BİY.12-ÜREME", "12", "Üreme", "Üreme ve gelişme süreçlerini açıklama/karşılaştırma.", ["açıklama", "karşılaştırma", "yorumlama"], ["açık uçlu soru", "şema"]),
            Outcome("BİY.12-GEN", "12", "Gen", "DNA, genetik bilgi, kalıtım, mutasyon ve biyoteknoloji süreçlerini değerlendirme.", ["yorumlama", "sorgulama", "değerlendirme"], ["açık uçlu soru", "veri analizi"]),
        ]
    return []


def parse_exact_grade_outcomes(program_text: str, selected_grade: str) -> List[Outcome]:
    text = program_text.replace("\r", "\n")
    pattern = re.compile(r"(BİY|BIY|Biy)\.(\d+)\.\d+\.\d+")
    matches = list(pattern.finditer(text))
    outcomes = []

    for i, m in enumerate(matches):
        g = m.group(2)
        if g != selected_grade:
            continue

        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else min(len(text), start + 1200)
        block = text[start:end].strip()
        code = m.group(0).replace("BIY", "BİY").replace("Biy", "BİY")

        prev = text[max(0, start - 800):start]
        theme = f"{selected_grade}. Sınıf"
        theme_match = re.findall(r"(?i)(\d+\.\s*TEMA\s*:\s*[^\n]+|TEMA\s*:\s*[^\n]+|ENERJİ|EKOLOJİ|YAŞAM|ORGANİZASYON|TEPKİ|HOMEOSTAZİ|ÜREME|GEN)", prev)
        if theme_match:
            theme = theme_match[-1].strip()

        clean = re.sub(r"\s+", " ", block)
        outcome_text = clean[:500]

        process_words = ["açıklama", "karşılaştırma", "yorumlama", "çıkarım", "çıkarım yapma", "gerekçelendirme", "sorgulama", "sınıflandırma", "değerlendirme", "neden-sonuç", "analiz", "ilişkilendirme"]
        processes = []
        for pw in process_words:
            if pw in norm(block) and pw not in processes:
                processes.append(pw)

        evidence_words = ["açık uçlu", "grafik", "tablo", "performans", "rubrik", "kontrol listesi", "gözlem", "deney", "rapor"]
        evidences = []
        for ew in evidence_words:
            if ew in norm(block):
                evidences.append(ew)

        outcomes.append(Outcome(code, selected_grade, theme, outcome_text, processes or ["belirlenecek"], evidences or ["açık uçlu soru"]))

    if not outcomes or len(outcomes) > 40:
        return fallback_outcomes_for_grade(selected_grade)

    return outcomes


def word_overlap(a: str, b: str) -> float:
    stop = {"ve", "ile", "bir", "bu", "şu", "için", "olan", "gibi", "soru", "açık", "uçlu", "ders", "tema", "öğrenme", "çıktısı", "bilgi"}
    wa = [w for w in re.sub(r"[^\wçğıöşüİıÇĞÖŞÜ]+", " ", norm(a)).split() if len(w) > 3 and w not in stop]
    wb = set(w for w in re.sub(r"[^\wçğıöşüİıÇĞÖŞÜ]+", " ", norm(b)).split() if len(w) > 3 and w not in stop)
    if not wa or not wb:
        return 0.0
    return sum(1 for w in wa if w in wb) / max(1, min(len(wa), len(wb)))


def raw_match_score(question: str, outcome: Outcome) -> float:
    combined = f"{outcome.code} {outcome.theme} {outcome.text} {' '.join(outcome.processes)} {' '.join(outcome.evidences)}"
    score = word_overlap(question, combined)
    qt = norm(question)
    cn = norm(combined)

    kw_boosts = [
        ("fermantasyon", .18), ("laktik", .12), ("etil alkol", .12), ("enerji", .10), ("solunum", .10), ("fotosentez", .10),
        ("ekosistem", .16), ("popülasyon", .16), ("süksesyon", .18), ("madde döngüsü", .18), ("rekabet", .16),
        ("simbiyotik", .18), ("besin zinciri", .18), ("besin ağı", .18), ("biyokütle", .14), ("grafik", .10), ("tablo", .10),
        ("taşıma kapasitesi", .18), ("çevresel direnç", .18)
    ]
    for kw, boost in kw_boosts:
        if kw in qt and kw in cn:
            score += boost

    if has_any(combined, ["embriyonik", "kalıtım", "dna", "genetik", "üreme"]) and has_any(question, ["ekosistem", "popülasyon", "süksesyon", "fermantasyon", "besin zinciri", "rekabet", "simbiyotik", "biyokütle"]):
        score -= .50

    return max(0.0, min(score, 1.0))


def best_match(question: str, selected_outcomes: List[Outcome]) -> Tuple[Outcome, float]:
    scored = [(o, raw_match_score(question, o)) for o in selected_outcomes]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0]


def detect_skills(t: str) -> List[str]:
    checks = [
        ("Karşılaştırma", ["karşılaştır", "fark", "benzer", "kıyas"]),
        ("Yorumlama", ["yorum", "grafik", "tablo", "veri", "inceleyiniz"]),
        ("Gerekçelendirme", ["gerekçe", "gerekçelendir", "neden", "kanıt"]),
        ("Neden-Sonuç", ["neden-sonuç", "neden sonuç", "etki", "sonuç", "mekanizma"]),
        ("Çıkarım Yapma", ["çıkarım", "sonuç çıkar", "ulaşılır", "etkisini açıklayınız"]),
        ("Problem Çözme", ["problem", "çözüm", "karar", "nasıl"]),
        ("Modelleme/Grafik", ["grafiği çiz", "model", "şema", "çiziniz"]),
        ("Deney Tasarlama", ["deney", "hipotez", "değişken"]),
        ("Sınıflandırma", ["sınıflandır", "çeşitlerini", "türlerini"]),
        ("Değerlendirme", ["değerlendir", "hangisi daha uygun", "uygun mudur"]),
        ("İlişkilendirme", ["ilişkilendir", "arasındaki ilişki", "ilişkisini"])
    ]
    skills = [name for name, ws in checks if has_any(t, ws)]
    return skills or ["Bilgi/Kavram Yoklama"]


def detect_evidence(t: str) -> List[str]:
    ev = ["Açık uçlu yanıt"]
    if has_any(t, ["tablo", "veri"]):
        ev.append("Tablo/veri analizi")
    if has_any(t, ["grafik", "grafiği çiz"]):
        ev.append("Grafik yorumlama/çizme")
    if has_any(t, ["gerekçe", "gerekçelendir"]):
        ev.append("Gerekçeli açıklama")
    if has_any(t, ["besin zinciri", "besin ağı"]):
        ev.append("Besin ağı/şema")
    return ev


PROCESS_ALIASES = {
    "açıklama": ["açıkla", "açıklayınız", "ifade", "yazınız", "tanımla"],
    "karşılaştırma": ["karşılaştır", "fark", "benzer", "kıyas"],
    "yorumlama": ["yorum", "grafik", "tablo", "veri", "inceleyiniz"],
    "çıkarım": ["çıkarım", "sonuç çıkar", "ulaşılır"],
    "çıkarım yapma": ["çıkarım", "sonuç çıkar", "ulaşılır"],
    "gerekçelendirme": ["gerekçe", "gerekçelendir", "kanıt", "neden"],
    "sorgulama": ["sorgula", "nasıl", "neden", "hangi değişken"],
    "sınıflandırma": ["sınıflandır", "çeşit", "tür", "grup"],
    "değerlendirme": ["değerlendir", "uygun", "hangisi", "karar"],
    "neden-sonuç": ["neden-sonuç", "neden sonuç", "etki", "sonuç", "mekanizma"],
    "analiz": ["analiz", "incele", "yorumla", "mekanizma", "ilişki"],
    "ilişkilendirme": ["ilişkilendir", "arasındaki ilişki", "ilişkisini"]
}


def match_process_components(question_text: str, outcome_processes: List[str], detected_skills: List[str]):
    if not outcome_processes or outcome_processes == ["belirlenecek"]:
        return [], outcome_processes

    qn = norm(question_text)
    skilln = " ".join(norm(s) for s in detected_skills)
    matched = []
    missing = []

    for process in outcome_processes:
        pn = norm(process)
        aliases = PROCESS_ALIASES.get(pn, [pn])
        direct = any(norm(a) in qn for a in aliases)
        via_skill = pn in skilln or any(norm(a) in skilln for a in aliases)

        if pn == "analiz" and has_any(question_text, ["mekanizma", "ilişki", "yorumlayınız", "inceleyiniz"]):
            direct = True
        if pn == "değerlendirme" and has_any(question_text, ["uygun", "hangisi", "karar", "tercih"]):
            direct = True

        if direct or via_skill:
            matched.append(process)
        else:
            missing.append(process)

    return matched, missing


def improvement_suggestion(question_text: str, matched: List[str], missing: List[str], evidence: List[str]) -> str:
    if not missing:
        return "Soru, hedef çıktının süreç bileşenlerini güçlü biçimde temsil ediyor. Beklenen cevap ve rubrik eklenirse değerlendirme güvenirliği artar."

    suggestions = []
    if any(norm(x) in ["gerekçelendirme"] for x in missing):
        suggestions.append('Yönergeye “Cevabınızı bilimsel gerekçelerle açıklayınız.” ifadesi eklenebilir.')
    if any(norm(x) in ["değerlendirme"] for x in missing):
        suggestions.append('Öğrenciden iki seçenek/durum arasında karar vermesi ve karar ölçütlerini belirtmesi istenebilir.')
    if any(norm(x) in ["karşılaştırma"] for x in missing):
        suggestions.append('İki durum, süreç veya canlı ilişkisi karşılaştırmalı biçimde sunulabilir.')
    if any(norm(x) in ["çıkarım", "çıkarım yapma"] for x in missing):
        suggestions.append('Kısa bir veri, grafik veya gözlem sonucu verilerek öğrenciden çıkarım yapması istenebilir.')
    if any(norm(x) in ["yorumlama", "analiz"] for x in missing):
        suggestions.append('Soruya tablo/grafik/senaryo eklenerek öğrencinin veriyi yorumlaması sağlanabilir.')
    if any(norm(x) in ["sorgulama"] for x in missing):
        suggestions.append('“Bu sonucun ortaya çıkmasında hangi değişkenler etkili olabilir?” gibi sorgulayıcı alt soru eklenebilir.')

    if not suggestions:
        suggestions.append("Eksik süreç bileşenlerini görünür kılmak için soru yönergesine daha açık işlem fiilleri eklenebilir.")

    if len(evidence) <= 1:
        suggestions.append("Öğrenme kanıtını güçlendirmek için grafik, tablo, kısa senaryo veya beklenen cevap rubriği eklenebilir.")

    return " ".join(suggestions)


def quality_level(score: int) -> str:
    if score >= 82:
        return "🟢 Güçlü"
    if score >= 68:
        return "🟡 Geliştirilebilir"
    return "🔴 Desteklenmeli"


def analyze_question(q: Question, selected_outcomes: List[Outcome], selected_grade: str) -> Dict:
    primary, raw_score = best_match(q.text, selected_outcomes)

    if primary.grade != selected_grade or code_grade(primary.code) not in ("", selected_grade):
        primary = fallback_outcomes_for_grade(selected_grade)[0]
        raw_score = 0.0

    skills = detect_skills(q.text)
    evidence = detect_evidence(q.text)
    matched_processes, missing_processes = match_process_components(q.text, primary.processes, skills)
    total_processes = len(primary.processes) if primary.processes and primary.processes != ["belirlenecek"] else 0
    process_count_text = f"{len(matched_processes)}/{total_processes}" if total_processes else "Belirsiz"

    program_fit = min(35, round(raw_score * 100))
    process_fit = 10 + (len(matched_processes) * 3) if total_processes else 10
    evidence_fit = 12 if evidence else 6
    context_score = 13 if len(q.text) > 160 else 8
    subpart_bonus = min(5, len(q.subparts)) if q.subparts else 0
    score = max(35, min(96, program_fit + process_fit + evidence_fit + context_score + subpart_bonus + 20))

    risks = []
    if raw_score < 0.08:
        risks.append("Seçilen sınıf çıktısıyla eşleşme zayıf; hedef çıktı öğretmen kılavuzunda açık belirtilmeli.")
    if total_processes and len(matched_processes) == 0:
        risks.append("Eşleşen süreç bileşeni yok; soru yönergesi süreç bileşenlerini daha açık yansıtmalı.")
    elif total_processes and missing_processes:
        risks.append("Bazı süreç bileşenleri desteklenebilir: " + ", ".join(missing_processes))
    if not has_any(q.text, ["tablo", "grafik", "veri", "durum", "örnek"]):
        risks.append("Bağlam/veri kullanımı artırılabilir.")

    return {
        "no": q.no,
        "text": q.text,
        "subparts": q.subparts,
        "primary": primary,
        "raw_score": raw_score,
        "skills": skills,
        "evidence": evidence,
        "matched_processes": matched_processes,
        "missing_processes": missing_processes,
        "process_count": process_count_text,
        "score": score,
        "quality": quality_level(score),
        "risks": risks,
        "suggestion": improvement_suggestion(q.text, matched_processes, missing_processes, evidence)
    }


def outcome_label(o: Outcome) -> str:
    short = o.text[:120].replace("\n", " ")
    return f"{o.code} | {o.theme} | {short}"


def process_density(analyses):
    c = Counter()
    for a in analyses:
        for p in a["matched_processes"]:
            c[p] += 1
    return c


def overall_quality(score, process_coverage):
    if score >= 82 and process_coverage >= .70:
        return "🟢 Güçlü"
    if score >= 65 or process_coverage >= .45:
        return "🟡 Geliştirilebilir"
    return "🔴 Desteklenmeli"


def global_development_notes(process_counter, process_coverage, analyses):
    notes = []
    if not process_counter:
        notes.append("Süreç bileşenleri görünürlüğü zayıf. Soru yönergelerinde açıklama, yorumlama, gerekçelendirme, çıkarım yapma gibi işlem fiilleri daha açık kullanılabilir.")
    else:
        common = ", ".join([p for p, n in process_counter.most_common(3)])
        notes.append(f"Yazılıda en çok temsil edilen süreçler: {common}. Süreç çeşitliliği dengelenebilir.")

    if process_coverage < .50:
        notes.append("Hedef öğrenme çıktılarının süreç bileşenlerinin yarısından azı görünür biçimde ölçülmüş. Eksik süreç bileşenlerine yönelik alt maddeler eklenebilir.")
    elif process_coverage < .75:
        notes.append("Süreç bileşenlerinin önemli bir kısmı ölçülmüş; ancak bazı süreçler desteklenebilir.")
    else:
        notes.append("Süreç bileşeni kapsaması güçlü görünüyor. Rubrik ve beklenen cevaplar eklenirse yazılı daha güvenilir hale gelir.")

    if any("Bağlam/veri" in " ".join(a["risks"]) for a in analyses):
        notes.append("Bazı sorulara kısa senaryo, tablo, grafik veya gözlem verisi eklenerek TYMM uyumu artırılabilir.")

    return notes


st.set_page_config(page_title="TYMM v8 Ana Soru Tek Yorum", layout="wide")
st.title("TYMM Program Tabanlı Yazılı Geliştirme Asistanı")
st.caption(APP_VERSION)
st.info("Bu sürümde ana soru tek yorum alır. a), b), c) alt maddeleri aynı ana soru altında değerlendirilir.")

st.sidebar.header("1. Program PDF")
program_pdf = st.sidebar.file_uploader("Öğretim Programı PDF", type=["pdf"])

st.sidebar.header("2. Sınıf Seviyesi")
ders = st.sidebar.selectbox("Ders", ["Biyoloji", "Kimya", "Fizik", "Matematik", "Türk Dili ve Edebiyatı"])
sinif = st.sidebar.selectbox("Sınıf Düzeyi", ["9. Sınıf", "10. Sınıf", "11. Sınıf", "12. Sınıf"], index=1)

st.sidebar.header("3. Yazılı PDF")
exam_pdf = st.sidebar.file_uploader("Yazılı PDF", type=["pdf"])

selected_grade = grade_no(sinif)
program_text = None
selected_outcomes = []

if program_pdf:
    with st.spinner("Program PDF okunuyor ve seçilen sınıf çıktıları çıkarılıyor..."):
        program_text = read_pdf(program_pdf)
        selected_outcomes = parse_exact_grade_outcomes(program_text, selected_grade)
        selected_outcomes = [o for o in selected_outcomes if o.grade == selected_grade and (code_grade(o.code) in ("", selected_grade))]
        if not selected_outcomes:
            selected_outcomes = fallback_outcomes_for_grade(selected_grade)

if not program_pdf:
    st.warning("Önce öğretim programı PDF’ini yükleyin.")
else:
    st.success(f"{sinif} için {len(selected_outcomes)} öğrenme çıktısı/kazanım hazırlandı.")

    with st.expander("İsteğe bağlı: Sınav senaryosu / hedef kazanım seçimi"):
        st.caption("Boş bırakırsanız sistem tüm sınıf çıktıları içinden otomatik analiz yapar. Seçerseniz analiz özellikle bu hedeflere göre yapılır.")
        label_to_outcome = {outcome_label(o): o for o in selected_outcomes}
        selected_labels = st.multiselect(
            "Bu yazılıda özellikle hedeflenen öğrenme çıktıları/kazanımlar",
            options=list(label_to_outcome.keys()),
            default=[],
        )

    target_outcomes = [label_to_outcome[l] for l in selected_labels] if selected_labels else selected_outcomes

    if selected_labels:
        st.info(f"Hedefli analiz modu açık: {len(target_outcomes)} hedef kazanım seçildi.")
    else:
        st.info("Otomatik analiz modu açık: Seçilen sınıfın tüm kazanımları dikkate alınacak.")

    run = st.button("Yazılıyı Analiz Et ve Geliştirme Raporu Oluştur", type="primary")

    if run:
        if not exam_pdf:
            st.error("Lütfen yazılı PDF’ini yükleyin.")
        else:
            with st.spinner("Yazılı okunuyor; ana soru ve alt maddeler ayrıştırılıyor..."):
                exam_text = read_pdf(exam_pdf)
                questions = split_questions(exam_text)
                analyses = [analyze_question(q, target_outcomes, selected_grade) for q in questions]

                avg = round(sum(a["score"] for a in analyses) / len(analyses)) if analyses else 0
                covered_target_codes = set(a["primary"].code for a in analyses)
                missing_targets = [o for o in target_outcomes if o.code not in covered_target_codes]
                target_coverage = len(covered_target_codes) / max(1, len(target_outcomes))

                target_process_map = {o.code: set(o.processes) for o in target_outcomes}
                measured_process_map = {o.code: set() for o in target_outcomes}

                for a in analyses:
                    code = a["primary"].code
                    if code in measured_process_map:
                        measured_process_map[code].update(a["matched_processes"])

                all_target_processes = sum(len(v) for v in target_process_map.values())
                all_measured_processes = sum(len(measured_process_map[k]) for k in measured_process_map)
                process_coverage = all_measured_processes / max(1, all_target_processes)

                score = max(0, min(100, avg + (5 if target_coverage > .75 else -8 if target_coverage < .5 else 0) + (5 if process_coverage > .75 else -8 if process_coverage < .5 else 0) - 4))
                p_counter = process_density(analyses)
                oq = overall_quality(score, process_coverage)
                notes = global_development_notes(p_counter, process_coverage, analyses)

            st.success(f"Analiz tamamlandı. {len(questions)} ana soru algılandı. Alt maddeler ana soru içinde değerlendirildi.")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Genel Durum", oq)
            c2.metric("Ana Soru", len(questions))
            c3.metric("Kazanım Kapsama", f"%{round(target_coverage*100)}")
            c4.metric("Süreç Kapsama", f"%{round(process_coverage*100)}")

            st.subheader("Genel Geliştirme Yorumu")
            for n in notes:
                st.write("•", n)

            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                "Soru Bazlı Geliştirme",
                "Ana Soru / Alt Madde Kontrolü",
                "Süreç Yoğunluğu",
                "Kazanım-Süreç Kapsama",
                "Öğretmen Kılavuzu",
                "Metin Raporu"
            ])

            with tab1:
                st.subheader("Soru Bazlı Geliştirme Önerileri")
                rows = []
                for a in analyses:
                    rows.append({
                        "Ana Soru": a["no"],
                        "Alt Madde Sayısı": len(a["subparts"]),
                        "Öğrenme Çıktısı": a["primary"].code,
                        "Süreç Eşleşmesi": a["process_count"],
                        "Eşleşen Süreçler": ", ".join(a["matched_processes"]) if a["matched_processes"] else "-",
                        "Desteklenebilecek Süreçler": ", ".join(a["missing_processes"]) if a["missing_processes"] else "-",
                        "Durum": a["quality"],
                        "Geliştirme Önerisi": a["suggestion"],
                    })
                st.dataframe(rows, use_container_width=True)

                for a in analyses:
                    with st.expander(f"Soru {a['no']} — {a['quality']} — süreç: {a['process_count']}"):
                        st.write("**Soru metni:**")
                        st.write(a["text"])
                        if a["subparts"]:
                            st.write("**Algılanan alt maddeler:**")
                            for sp in a["subparts"]:
                                st.write("-", sp[:300])
                        st.write("**Eşleşen öğrenme çıktısı:**", a["primary"].code, "-", a["primary"].text)
                        st.write("**Eşleşen süreçler:**", ", ".join(a["matched_processes"]) if a["matched_processes"] else "Yok")
                        st.write("**Desteklenebilecek süreçler:**", ", ".join(a["missing_processes"]) if a["missing_processes"] else "Yok")
                        st.write("**Yazılıyı güçlendirme önerisi:**")
                        st.success(a["suggestion"])

            with tab2:
                st.subheader("Ana Soru / Alt Madde Kontrolü")
                st.caption("Her satır bir ana sorudur. a), b), c) alt maddeleri varsa aynı ana soru altında kalır.")
                st.dataframe([
                    {
                        "Ana Soru": q.no,
                        "Alt Madde Sayısı": len(q.subparts),
                        "Alt Maddeler": " | ".join([sp[:120] for sp in q.subparts]) if q.subparts else "-",
                        "Metin Önizleme": q.text[:250]
                    }
                    for q in questions
                ], use_container_width=True)

            with tab3:
                st.subheader("Süreç Yoğunluk Analizi")
                if p_counter:
                    st.dataframe([
                        {"Süreç Bileşeni": p, "Görünme Sayısı": n}
                        for p, n in p_counter.most_common()
                    ], use_container_width=True)
                else:
                    st.warning("Süreç bileşeni eşleşmesi bulunamadı.")

            with tab4:
                st.subheader("Kazanım - Süreç Bileşeni Kapsama")
                coverage_rows = []
                for o in target_outcomes:
                    target_ps = target_process_map[o.code]
                    measured_ps = measured_process_map[o.code]
                    coverage_rows.append({
                        "Öğrenme Çıktısı": o.code,
                        "Tema": o.theme,
                        "Hedef Süreçler": ", ".join(sorted(target_ps)),
                        "Ulaşılan Süreçler": ", ".join(sorted(measured_ps)) if measured_ps else "-",
                        "Desteklenebilecek Süreçler": ", ".join(sorted(target_ps - measured_ps)) if target_ps - measured_ps else "-",
                        "Kapsama": f"{len(measured_ps)}/{len(target_ps)}" if target_ps else "Belirsiz",
                        "Ölçen Sorular": ", ".join(map(str, [a["no"] for a in analyses if a["primary"].code == o.code])) or "-"
                    })
                st.dataframe(coverage_rows, use_container_width=True)

                if missing_targets:
                    st.warning("Bazı öğrenme çıktıları yazılıda ana eşleşme olarak görünmedi:")
                    for m in missing_targets:
                        st.write("-", m.code, m.text)

            with tab5:
                st.subheader("Öğretmen TYMM Kılavuzu")
                guide = []
                for a in analyses:
                    guide.append({
                        "Ana Soru": a["no"],
                        "Alt Madde Sayısı": len(a["subparts"]),
                        "Öğrenme Çıktısı": a["primary"].code,
                        "Süreç Bileşeni Sayısı": a["process_count"],
                        "Eşleşen Süreçler": ", ".join(a["matched_processes"]) if a["matched_processes"] else "-",
                        "Desteklenebilecek Süreçler": ", ".join(a["missing_processes"]) if a["missing_processes"] else "-",
                        "Öğrenme Kanıtı": ", ".join(a["evidence"]),
                        "Geliştirici Not": a["suggestion"]
                    })
                st.dataframe(guide, use_container_width=True)

            with tab6:
                report = []
                report.append("TYMM YAZILI GELİŞTİRME RAPORU")
                report.append(f"Uygulama sürümü: {APP_VERSION}")
                report.append(f"Ders: {ders}")
                report.append(f"Sınıf: {sinif}")
                report.append(f"Genel Durum: {oq}")
                report.append(f"Ana Soru Sayısı: {len(questions)}")
                report.append(f"Kazanım Kapsama: %{round(target_coverage*100)}")
                report.append(f"Süreç Bileşeni Kapsama: %{round(process_coverage*100)}")
                report.append("")
                report.append("Genel geliştirme notları:")
                for n in notes:
                    report.append(f"- {n}")
                report.append("")
                report.append("Soru bazlı geliştirme:")
                for a in analyses:
                    report.append(f"Soru {a['no']}: Alt madde: {len(a['subparts'])} | {a['primary'].code} | Süreç: {a['process_count']} | Eşleşen: {', '.join(a['matched_processes']) or '-'} | Desteklenebilecek: {', '.join(a['missing_processes']) or '-'} | Öneri: {a['suggestion']}")
                report_text = "\n".join(report)
                st.text_area("Rapor", report_text, height=420)
                st.download_button("Metin Raporu İndir", report_text, file_name="tymm_yazili_gelistirme_raporu.txt")
