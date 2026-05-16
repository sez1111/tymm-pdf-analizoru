
import re
from dataclasses import dataclass
from typing import List, Tuple, Dict
import streamlit as st
import fitz

APP_VERSION = "v4 - SEÇİLİ SINIF KİLİTLİ SÜRÜM"


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


def split_questions(text: str) -> List[Question]:
    t = text.replace("\r", "\n")
    t = re.sub(r"\s+(\d{1,2})[\.\)]\s+", r"\n\1. ", t)
    matches = list(re.finditer(r"(?:^|\n)\s*(\d{1,2})[\.\)]\s+", t))
    if not matches:
        return [Question(1, t.strip())] if t.strip() else []

    questions = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(t)
        body = t[start:end].strip()
        if body:
            questions.append(Question(int(m.group(1)), body))
    return questions


def fallback_outcomes_for_grade(grade: str) -> List[Outcome]:
    # These are safe grade-locked groups used when PDF parsing is messy.
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
    """
    Strict parser: scans the whole program text but only accepts BİY.<selected_grade>.* codes.
    This avoids bad section slicing and prevents BİY.12.* from entering 10th grade results.
    """
    text = program_text.replace("\r", "\n")
    # Split by all BİY.x.y.z codes while keeping code.
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

        # Theme inference from nearby previous text
        prev = text[max(0, start - 800):start]
        theme = f"{selected_grade}. Sınıf"
        theme_match = re.findall(r"(?i)(\d+\.\s*TEMA\s*:\s*[^\n]+|TEMA\s*:\s*[^\n]+|ENERJİ|EKOLOJİ|YAŞAM|ORGANİZASYON|TEPKİ|HOMEOSTAZİ|ÜREME|GEN)", prev)
        if theme_match:
            theme = theme_match[-1].strip()

        # Keep first part as outcome text
        clean = re.sub(r"\s+", " ", block)
        outcome_text = clean[:500]

        processes = []
        evidences = []

        # Try to infer processes from block
        process_words = ["açıklama", "karşılaştırma", "yorumlama", "çıkarım", "gerekçelendirme", "sorgulama", "sınıflandırma", "değerlendirme", "neden-sonuç", "analiz"]
        for pw in process_words:
            if pw in norm(block):
                processes.append(pw)

        evidence_words = ["açık uçlu", "grafik", "tablo", "performans", "rubrik", "kontrol listesi", "gözlem", "deney", "rapor"]
        for ew in evidence_words:
            if ew in norm(block):
                evidences.append(ew)

        outcomes.append(Outcome(code, selected_grade, theme, outcome_text, processes or ["belirlenecek"], evidences or ["açık uçlu soru"]))

    # If parser creates too many garbage rows, use fallback groups. But all fallback codes are selected-grade locked.
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

    # Hard anti-mismatch for selected-grade ecology/energy vs genetics/embryology words in unrelated outcome
    if has_any(combined, ["embriyonik", "kalıtım", "dna", "genetik", "üreme"]) and has_any(question, ["ekosistem", "popülasyon", "süksesyon", "fermantasyon", "besin zinciri", "rekabet", "simbiyotik", "biyokütle"]):
        score -= .50

    return max(0.0, min(score, 1.0))


def best_match(question: str, selected_outcomes: List[Outcome]) -> Tuple[Outcome, float]:
    # selected_outcomes already contains only chosen grade. Never use other grades here.
    scored = [(o, raw_match_score(question, o)) for o in selected_outcomes]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0]


def detect_skills(t: str) -> List[str]:
    checks = [
        ("Karşılaştırma", ["karşılaştır", "fark", "benzer"]),
        ("Yorumlama", ["yorum", "grafik", "tablo", "veri"]),
        ("Gerekçelendirme", ["gerekçe", "gerekçelendir", "neden"]),
        ("Neden-Sonuç", ["neden-sonuç", "etki", "sonuç", "mekanizma"]),
        ("Problem Çözme", ["problem", "çözüm", "karar"]),
        ("Modelleme/Grafik", ["grafiği çiz", "model", "şema", "çiziniz"]),
        ("Deney Tasarlama", ["deney", "hipotez", "değişken"]),
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


def analyze_question(q: Question, selected_outcomes: List[Outcome], selected_grade: str) -> Dict:
    primary, raw_score = best_match(q.text, selected_outcomes)

    # Absolute safety check
    if primary.grade != selected_grade or code_grade(primary.code) not in ("", selected_grade):
        primary = fallback_outcomes_for_grade(selected_grade)[0]
        raw_score = 0.0

    skills = detect_skills(q.text)
    evidence = detect_evidence(q.text)

    program_fit = min(35, round(raw_score * 100))
    process_fit = 15
    evidence_fit = 12 if evidence else 6
    context_score = 13 if len(q.text) > 160 else 8
    score = max(35, min(96, program_fit + process_fit + evidence_fit + context_score + 20))

    risks = []
    if raw_score < 0.08:
        risks.append("Seçilen sınıf çıktısıyla eşleşme zayıf; hedef çıktı öğretmen kılavuzunda açık belirtilmeli.")
    if not has_any(q.text, ["açıklayınız", "yorumlayınız", "gerekçelendir", "karşılaştır"]):
        risks.append("Süreç bileşeni görünürlüğü zayıf olabilir.")
    if not has_any(q.text, ["tablo", "grafik", "veri", "durum", "örnek"]):
        risks.append("Bağlam/veri kullanımı artırılabilir.")

    return {
        "no": q.no,
        "text": q.text,
        "primary": primary,
        "raw_score": raw_score,
        "skills": skills,
        "evidence": evidence,
        "score": score,
        "status": "Güçlü" if score >= 82 else "Geliştirilebilir" if score >= 68 else "Zayıf",
        "risks": risks,
    }


st.set_page_config(page_title="TYMM v4 Seçili Sınıf Kilitli", layout="wide")
st.title("TYMM Program Tabanlı Yazılı Analizörü")
st.caption(APP_VERSION)
st.warning("Bu sürümde ana eşleşme seçili sınıf dışına çıkamaz. 10. sınıf seçildiyse BİY.12.* ana eşleşme olarak görünmemelidir.")

st.sidebar.header("1. Program PDF")
program_pdf = st.sidebar.file_uploader("Öğretim Programı PDF", type=["pdf"])

st.sidebar.header("2. Yazılı PDF")
exam_pdf = st.sidebar.file_uploader("Yazılı PDF", type=["pdf"])

st.sidebar.header("3. Sınıf Seviyesi")
ders = st.sidebar.selectbox("Ders", ["Biyoloji", "Kimya", "Fizik", "Matematik", "Türk Dili ve Edebiyatı"])
sinif = st.sidebar.selectbox("Sınıf Düzeyi", ["9. Sınıf", "10. Sınıf", "11. Sınıf", "12. Sınıf"], index=1)

run = st.sidebar.button("Seçili Sınıfa Göre Analiz Et", type="primary")

if run:
    if not program_pdf or not exam_pdf:
        st.error("Lütfen program PDF'ini ve yazılı PDF'ini yükleyin.")
    else:
        selected_grade = grade_no(sinif)
        with st.spinner("Program okunuyor ve seçili sınıfa kilitlenmiş analiz yapılıyor..."):
            program_text = read_pdf(program_pdf)
            exam_text = read_pdf(exam_pdf)
            selected_outcomes = parse_exact_grade_outcomes(program_text, selected_grade)

            # Final security filter
            selected_outcomes = [o for o in selected_outcomes if o.grade == selected_grade and (code_grade(o.code) in ("", selected_grade))]
            if not selected_outcomes:
                selected_outcomes = fallback_outcomes_for_grade(selected_grade)

            questions = split_questions(exam_text)
            analyses = [analyze_question(q, selected_outcomes, selected_grade) for q in questions]

            avg = round(sum(a["score"] for a in analyses) / len(analyses)) if analyses else 0
            covered = set(a["primary"].code for a in analyses)
            missing = [o for o in selected_outcomes if o.code not in covered]
            coverage = len(covered) / max(1, len(selected_outcomes))
            score = max(0, min(100, avg + (4 if coverage > .75 else -8 if coverage < .5 else 0) - 4))

        st.success(f"Analiz tamamlandı. Ana eşleşme sadece {sinif} çıktılarıyla yapıldı.")

        # Diagnostics: show if any wrong grade slipped in.
        wrong = [a for a in analyses if a["primary"].grade != selected_grade or code_grade(a["primary"].code) not in ("", selected_grade)]
        if wrong:
            st.error("Güvenlik filtresine rağmen seçili sınıf dışı sonuç var. Bu satırlar rapordan çıkarılmalı.")
        else:
            st.success("Sınıf kilidi kontrolü başarılı: ana eşleşmelerde seçili sınıf dışı kod yok.")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Genel Uyum", f"{score}/100")
        c2.metric("Soru", len(questions))
        c3.metric(f"{sinif} Çıktısı", len(selected_outcomes))
        c4.metric("Seçili Sınıf Kapsama", f"%{round(coverage*100)}")

        tab1, tab2, tab3, tab4 = st.tabs([
            "Soru Eşleştirme",
            f"{sinif} Çıktı-Soru Matrisi",
            "Öğretmen Kılavuzu",
            "PDF Metinleri"
        ])

        with tab1:
            st.subheader("Soru Bazlı Eşleştirme")
            rows = []
            for a in analyses:
                rows.append({
                    "Soru": a["no"],
                    "Ana Eşleşme": a["primary"].code,
                    "Ana Sınıf": a["primary"].grade,
                    "Tema": a["primary"].theme,
                    "Beceri": ", ".join(a["skills"]),
                    "Kanıt": ", ".join(a["evidence"]),
                    "Durum": a["status"],
                    "Puan": a["score"],
                    "Risk": " | ".join(a["risks"]) if a["risks"] else "Seçili sınıfa göre uygun görünüyor."
                })
            st.dataframe(rows, use_container_width=True)

            for a in analyses:
                with st.expander(f"Soru {a['no']} ayrıntısı"):
                    st.write(a["text"])
                    st.write("**Ana eşleşme:**", a["primary"].code, f"({a['primary'].grade}. sınıf)", "-", a["primary"].text)

        with tab2:
            st.subheader(f"{sinif} Öğrenme Çıktısı - Soru Matrisi")
            matrix = []
            for o in selected_outcomes:
                qs = [a["no"] for a in analyses if a["primary"].code == o.code]
                matrix.append({
                    "Öğrenme Çıktısı": o.code,
                    "Tema": o.theme,
                    "Ölçen Sorular": ", ".join(map(str, qs)) if qs else "-",
                    "Durum": "Ölçüldü" if qs else "Ölçülmedi",
                    "Not": "Ana değerlendirme içinde temsil ediliyor." if qs else "Bu çıktı için soru/alt madde eklenebilir."
                })
            st.dataframe(matrix, use_container_width=True)
            if missing:
                st.warning(f"{sinif} içinde ölçülmeyen veya zayıf temsil edilen çıktılar var.")
                for m in missing:
                    st.write("-", m.code, m.text)

        with tab3:
            st.subheader("Öğretmen TYMM Kılavuzu")
            guide = []
            for a in analyses:
                guide.append({
                    "Soru": a["no"],
                    "Ana Öğrenme Çıktısı": a["primary"].code,
                    "Ana Sınıf": a["primary"].grade,
                    "Süreç Bileşeni": ", ".join(a["skills"]),
                    "Öğrenme Kanıtı": ", ".join(a["evidence"]),
                    "Kılavuz Notu": a["risks"][0] if a["risks"] else "Seçili sınıfa göre uygun görünüyor."
                })
            st.dataframe(guide, use_container_width=True)

            report = []
            report.append("TYMM PROGRAM TABANLI YAZILI ANALİZ RAPORU")
            report.append(f"Uygulama sürümü: {APP_VERSION}")
            report.append(f"Ders: {ders}")
            report.append(f"Sınıf: {sinif}")
            report.append(f"Genel Uyum: {score}/100")
            report.append("")
            for a in analyses:
                report.append(f"Soru {a['no']}: {a['primary'].code} ({a['primary'].grade}. sınıf) | {a['status']} | {a['score']}/100")
            st.download_button("Metin Raporu İndir", "\n".join(report), file_name="tymm_analiz_raporu.txt")

        with tab4:
            c1, c2 = st.columns(2)
            with c1:
                st.text_area("Tam Program Metni", program_text, height=500)
            with c2:
                st.text_area("Yazılı Metni", exam_text, height=500)
else:
    st.info("Sol menüde program PDF’ini, yazılı PDF’ini yükleyin ve sınıf düzeyini seçin.")
