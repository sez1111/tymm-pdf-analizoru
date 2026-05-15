
import re
from dataclasses import dataclass
from typing import List, Dict, Tuple

import streamlit as st

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None


@dataclass
class Outcome:
    code: str
    theme: str
    text: str
    processes: List[str]
    evidences: List[str]


@dataclass
class Question:
    no: int
    text: str


def read_pdf(uploaded_file) -> str:
    if fitz is None:
        raise RuntimeError("PyMuPDF kurulu değil.")
    data = uploaded_file.read()
    doc = fitz.open(stream=data, filetype="pdf")
    return "\n".join(page.get_text("text") for page in doc)


def normalize(text: str) -> str:
    return (text or "").lower().replace("ı", "i")


def has_any(text: str, words: List[str]) -> bool:
    t = normalize(text)
    return any(normalize(w) in t for w in words)


def split_questions(text: str) -> List[Question]:
    t = text.replace("\r", "\n").strip()
    matches = list(re.finditer(r"(?:^|\n)\s*(\d{1,2})[\.\)]\s+", t))
    if not matches:
        return [Question(1, t)] if t else []

    questions = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(t)
        q_text = t[start:end].strip()
        if q_text:
            questions.append(Question(int(match.group(1)), q_text))
    return questions


def fallback_program_outcomes(text: str) -> List[Outcome]:
    t = normalize(text)
    outcomes = []

    if any(k in t for k in ["enerji", "fermantasyon", "solunum", "fotosentez", "glikoz", "atp"]):
        outcomes.append(Outcome(
            code="BİY.10-ENERJİ",
            theme="Enerji",
            text="Canlılarda enerji dönüşümleri, solunum ve fermantasyon süreçlerini açıklama/karşılaştırma.",
            processes=["açıklama", "karşılaştırma", "çıkarım yapma", "gerekçelendirme"],
            evidences=["açık uçlu soru", "tablo yorumlama", "bilgi kartı analizi"],
        ))

    if any(k in t for k in ["ekoloji", "ekosistem", "popülasyon", "biyokütle", "madde döngüsü", "süksesyon"]):
        outcomes.append(Outcome(
            code="BİY.10-EKOLOJİ-1",
            theme="Ekoloji",
            text="Ekosistemde enerji akışı, madde döngüleri, biyokütle ve süksesyon ilişkilerini yorumlama.",
            processes=["yorumlama", "neden-sonuç kurma", "çıkarım yapma", "değerlendirme"],
            evidences=["grafik yorumlama", "açık uçlu soru", "senaryo analizi"],
        ))

    if any(k in t for k in ["rekabet", "simbiyotik", "besin zinciri", "besin ağı", "komünite"]):
        outcomes.append(Outcome(
            code="BİY.10-EKOLOJİ-2",
            theme="Ekoloji",
            text="Canlılar arasındaki ekolojik ilişkileri, rekabeti, simbiyozu ve besin ağlarını analiz etme.",
            processes=["sınıflandırma", "karşılaştırma", "gerekçelendirme", "analiz"],
            evidences=["açık uçlu soru", "grafik çizme", "besin ağı oluşturma"],
        ))

    if any(k in t for k in ["dna", "gen", "kalıtım", "mutasyon", "protein sentezi"]):
        outcomes.append(Outcome(
            code="BİY-GENETİK",
            theme="Genetik",
            text="Genetik bilgi, kalıtım ve biyoteknoloji süreçlerini yorumlama.",
            processes=["yorumlama", "sorgulama", "değerlendirme"],
            evidences=["açık uçlu soru", "veri analizi"],
        ))

    if not outcomes:
        outcomes.append(Outcome(
            code="PROGRAM-YAPISI-ALGILANAMADI",
            theme="Genel",
            text="Programdan net öğrenme çıktısı çıkarılamadı. İlgili tema/öğrenme çıktısı bölümü daha açık verilmelidir.",
            processes=["belirlenecek"],
            evidences=["belirlenecek"],
        ))

    return outcomes


def parse_program(text: str) -> List[Outcome]:
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    outcomes = []
    current_theme = "Belirtilmemiş Tema"
    current = None

    for line in lines:
        if re.match(r"^tema\s*:", line, flags=re.I):
            current_theme = re.sub(r"^tema\s*:", "", line, flags=re.I).strip()
            continue

        if re.search(r"(öğrenme çıktısı|BİY\.\d+|BIY\.\d+)", line, flags=re.I):
            if current:
                outcomes.append(current)
            code_match = re.search(r"(BİY|BIY|Biy)\.\d+\.\d+\.\d+", line)
            code = code_match.group(0).replace("BIY", "BİY").replace("Biy", "BİY") if code_match else "Kod belirtilmemiş"
            current = Outcome(
                code=code,
                theme=current_theme,
                text=re.sub(r"öğrenme çıktısı\s*:", "", line, flags=re.I).strip(),
                processes=[],
                evidences=[],
            )
            continue

        if current and re.search(r"süreç bileşen", line, flags=re.I):
            processes = re.sub(r"süreç bileşenleri\s*:", "", line, flags=re.I)
            current.processes = [x.strip() for x in re.split(r",|;", processes) if x.strip()]
            continue

        if current and re.search(r"öğrenme kanıt", line, flags=re.I):
            evidences = re.sub(r"öğrenme kanıtları\s*:", "", line, flags=re.I)
            current.evidences = [x.strip() for x in re.split(r",|;", evidences) if x.strip()]
            continue

    if current:
        outcomes.append(current)

    return outcomes if outcomes else fallback_program_outcomes(text)


def word_overlap(a: str, b: str) -> float:
    stop = {"ve", "ile", "bir", "bu", "şu", "için", "olan", "gibi", "soru", "açık", "uçlu", "ders", "tema", "öğrenme", "çıktısı"}
    words_a = [w for w in re.sub(r"[^\wçğıöşüİıÇĞÖŞÜ]+", " ", normalize(a)).split() if len(w) > 3 and w not in stop]
    words_b = set(w for w in re.sub(r"[^\wçğıöşüİıÇĞÖŞÜ]+", " ", normalize(b)).split() if len(w) > 3 and w not in stop)
    if not words_a or not words_b:
        return 0.0
    hits = sum(1 for w in words_a if w in words_b)
    return hits / max(1, min(len(words_a), len(words_b)))


def detect_skills(text: str) -> List[str]:
    checks = [
        ("Karşılaştırma", ["karşılaştır", "benzer", "fark", "kıyas"]),
        ("Yorumlama", ["yorumla", "yorumlayınız", "grafik", "tablo", "veri"]),
        ("Gerekçelendirme", ["gerekçe", "gerekçelendir", "neden", "kanıt"]),
        ("Çıkarım Yapma", ["çıkarım", "sonuç çıkar", "ulaşılır", "etkisini açıklayınız"]),
        ("Neden-Sonuç Kurma", ["neden-sonuç", "neden sonuç", "etki", "sonuç", "mekanizma"]),
        ("Problem Çözme", ["problem", "çözüm", "öneri", "nasıl çözülür", "karar ver"]),
        ("Modelleme / Grafik Oluşturma", ["grafiği çiz", "model", "şema", "çiziniz"]),
        ("Deney Tasarlama", ["deney tasarla", "hipotez", "değişken", "kontrollü deney", "bağımlı değişken", "bağımsız değişken"]),
    ]
    skills = [name for name, words in checks if has_any(text, words)]
    return skills or ["Bilgi / Kavram Yoklama"]


def detect_evidence(text: str) -> List[str]:
    ev = ["Açık uçlu yanıt"]
    if has_any(text, ["tablo", "veri"]):
        ev.append("Tablo / veri analizi")
    if has_any(text, ["grafik", "grafiği çiz"]):
        ev.append("Grafik yorumlama / çizme")
    if has_any(text, ["gerekçe", "gerekçelendir"]):
        ev.append("Gerekçeli açıklama")
    if has_any(text, ["deney", "hipotez", "değişken"]):
        ev.append("Deneysel düşünme")
    if has_any(text, ["besin zinciri", "besin ağı"]):
        ev.append("Şema / ağ oluşturma")
    return ev


def match_outcome(question_text: str, outcomes: List[Outcome]) -> Tuple[Outcome, float]:
    best = outcomes[0]
    best_score = -1.0
    for o in outcomes:
        combined = f"{o.theme} {o.code} {o.text} {' '.join(o.processes)} {' '.join(o.evidences)}"
        s = word_overlap(question_text, combined)

        qt = normalize(question_text)
        combined_norm = normalize(combined)
        for kw in ["fermantasyon", "enerji", "ekosistem", "popülasyon", "süksesyon", "madde döngüsü", "rekabet", "simbiyotik", "besin zinciri", "besin ağı", "grafik", "tablo"]:
            if kw in qt and kw in combined_norm:
                s += 0.10

        if s > best_score:
            best = o
            best_score = s

    return best, min(best_score, 1.0)


def analyze_question(q: Question, outcomes: List[Outcome]) -> Dict:
    outcome, match_score = match_outcome(q.text, outcomes)
    skills = detect_skills(q.text)
    evidence = detect_evidence(q.text)

    program_fit = min(30, round(match_score * 100))
    process_fit = 20 if any(any(normalize(p) in normalize(s) or normalize(s) in normalize(p) for p in outcome.processes) for s in skills) else 12
    evidence_fit = 15 if any(any(normalize(e) in normalize(v) or normalize(v) in normalize(e) for v in outcome.evidences) for e in evidence) else 9
    context_score = 15 if len(q.text) > 160 else 8
    clarity_score = 6 if len(q.text) > 700 else 12

    score = max(35, min(96, program_fit + process_fit + evidence_fit + context_score + clarity_score + 18))

    risks = []
    if match_score < 0.08:
        risks.append("Programdaki öğrenme çıktısıyla metinsel eşleşme zayıf; öğretmen kılavuzunda hedef çıktı açık belirtilmeli.")
    if not has_any(q.text, ["gerekçe", "gerekçelendir", "açıklayınız", "yorumlayınız", "karşılaştır"]):
        risks.append("Süreç bileşeni görünürlüğü zayıf olabilir.")
    if not has_any(q.text, ["tablo", "grafik", "veri", "senaryo", "örnek", "durum"]):
        risks.append("Bağlam / veri kullanımı artırılabilir.")
    if not has_any(q.text, ["deney", "hipotez", "değişken", "model", "çözüm"]):
        risks.append("Deney tasarlama, modelleme veya problem çözme boyutu eklenebilir.")
    if len(q.text) > 700:
        risks.append("Bilişsel yük yüksek; soru alt basamaklara ayrılabilir.")

    status = "Güçlü" if score >= 82 else "Geliştirilebilir" if score >= 68 else "Zayıf"

    return {
        "no": q.no,
        "question": q.text,
        "outcome": outcome,
        "match_score": match_score,
        "skills": skills,
        "evidence": evidence,
        "score": score,
        "status": status,
        "risks": risks,
    }


def analyze(program_text: str, exam_text: str):
    outcomes = parse_program(program_text)
    questions = split_questions(exam_text)
    analyses = [analyze_question(q, outcomes) for q in questions]

    score = round(sum(a["score"] for a in analyses) / len(analyses)) if analyses else 0
    covered_codes = set(a["outcome"].code for a in analyses)
    coverage_ratio = len(covered_codes) / max(1, len(outcomes))

    if coverage_ratio < 0.5:
        score -= 8
    elif coverage_ratio > 0.75:
        score += 4

    if "rubrik" not in normalize(exam_text) and "dereceli puanlama" not in normalize(exam_text):
        score -= 4

    score = max(0, min(100, score))
    missing = [o for o in outcomes if o.code not in covered_codes]
    return outcomes, questions, analyses, score, coverage_ratio, missing


st.set_page_config(page_title="TYMM PDF Analizörü", layout="wide")
st.title("TYMM Program Tabanlı PDF Yazılı Analizörü")
st.caption("Öğretim programı PDF’i ve yazılı PDF’i yüklenir; sistem yazılıyı programa göre değerlendirir.")

with st.sidebar:
    st.header("Yükleme")
    ders = st.selectbox("Ders", ["Biyoloji", "Kimya", "Fizik", "Matematik", "Türk Dili ve Edebiyatı"])
    sinif = st.selectbox("Sınıf Düzeyi", ["9. Sınıf", "10. Sınıf", "11. Sınıf", "12. Sınıf"], index=1)
    program_pdf = st.file_uploader("Öğretim Programı PDF", type=["pdf"])
    exam_pdf = st.file_uploader("Yazılı PDF", type=["pdf"])
    run = st.button("PDF'leri Oku ve Analiz Et", type="primary")

if run:
    if not program_pdf or not exam_pdf:
        st.error("Lütfen öğretim programı PDF’i ve yazılı PDF’ini birlikte yükleyin.")
    else:
        with st.spinner("PDF'ler okunuyor ve analiz ediliyor..."):
            program_text = read_pdf(program_pdf)
            exam_text = read_pdf(exam_pdf)
            outcomes, questions, analyses, score, coverage_ratio, missing = analyze(program_text, exam_text)

        st.success("Analiz tamamlandı.")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Genel Uyum Puanı", f"{score}/100")
        col2.metric("Algılanan Soru", len(questions))
        col3.metric("Program Çıktısı", len(outcomes))
        col4.metric("Kapsama", f"%{round(coverage_ratio*100)}")

        if score >= 80:
            st.info("Yazılı, yüklenen öğretim programına büyük ölçüde uyumlu görünüyor. Öğretmen kılavuzu ve rubrik katmanı güçlendirilebilir.")
        elif score >= 65:
            st.warning("Yazılıda program uyumu var; ancak bazı öğrenme çıktıları ve süreç bileşenleri daha görünür hale getirilmeli.")
        else:
            st.error("Yazılı, program öğrenme çıktılarıyla yeniden eşleştirilerek güçlendirilmeli.")

        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Programdan Çıkan Yapı",
            "Soru Bazlı Eşleştirme",
            "Çıktı-Soru Matrisi",
            "Öğretmen Kılavuzu",
            "PDF Metinleri"
        ])

        with tab1:
            st.subheader("Programdan Algılanan Öğrenme Çıktıları")
            st.dataframe([
                {
                    "Kod": o.code,
                    "Tema": o.theme,
                    "Öğrenme Çıktısı": o.text,
                    "Süreç Bileşenleri": ", ".join(o.processes),
                    "Öğrenme Kanıtları": ", ".join(o.evidences),
                }
                for o in outcomes
            ], use_container_width=True)

        with tab2:
            st.subheader("Soru Bazlı Program Eşleştirme")
            st.dataframe([
                {
                    "Soru": a["no"],
                    "Eşleşen Çıktı": a["outcome"].code,
                    "Tema": a["outcome"].theme,
                    "Süreç / Beceri": ", ".join(a["skills"]),
                    "Kanıt": ", ".join(a["evidence"]),
                    "Uyum": a["status"],
                    "Puan": a["score"],
                    "Gerekçe / Risk": " | ".join(a["risks"]) if a["risks"] else "Programla uyumlu görünüyor.",
                }
                for a in analyses
            ], use_container_width=True)

            for a in analyses:
                with st.expander(f"Soru {a['no']} ayrıntısı"):
                    st.write(a["question"])
                    st.write("**Eşleşen çıktı:**", a["outcome"].code, "-", a["outcome"].text)
                    st.write("**Süreç/Beceri:**", ", ".join(a["skills"]))
                    st.write("**Riskler:**")
                    if a["risks"]:
                        for r in a["risks"]:
                            st.write("-", r)
                    else:
                        st.write("- Belirgin risk yok.")

        with tab3:
            st.subheader("Öğrenme Çıktısı - Soru Matrisi")
            matrix = []
            for o in outcomes:
                qs = [a["no"] for a in analyses if a["outcome"].code == o.code]
                matrix.append({
                    "Öğrenme Çıktısı": o.code,
                    "Tema": o.theme,
                    "Ölçen Sorular": ", ".join(map(str, qs)) if qs else "-",
                    "Durum": "Ölçüldü" if qs else "Ölçülmedi",
                    "Not": "Temsil ediliyor." if qs else "Bu çıktı için soru/alt madde eklenebilir.",
                })
            st.dataframe(matrix, use_container_width=True)

            if missing:
                st.warning("Ölçülmeyen veya zayıf temsil edilen öğrenme çıktıları var.")
                for m in missing:
                    st.write("-", m.code, m.text)

        with tab4:
            st.subheader("Öğretmen TYMM Kılavuzu")
            st.caption("Bu bölüm öğrenci yazılı kağıdında görünmez; zümre/ölçme değerlendirme kontrolü için ayrı PDF mantığında kullanılır.")
            guide = []
            for a in analyses:
                guide.append({
                    "Soru": a["no"],
                    "Öğrenme Çıktısı": a["outcome"].code,
                    "Süreç Bileşeni": ", ".join(a["skills"]),
                    "Öğrenme Kanıtı": ", ".join(a["evidence"]),
                    "Rubrik Notu": "Açık uçlu soru için beklenen cevap ve dereceli puanlama anahtarı eklenmeli.",
                    "Geliştirme Notu": a["risks"][0] if a["risks"] else "Soru programla uyumlu görünüyor.",
                })
            st.dataframe(guide, use_container_width=True)

            report_text = []
            report_text.append("TYMM PROGRAM TABANLI YAZILI ANALİZ RAPORU")
            report_text.append(f"Ders: {ders}")
            report_text.append(f"Sınıf: {sinif}")
            report_text.append(f"Genel Uyum Puanı: {score}/100")
            report_text.append(f"Soru Sayısı: {len(questions)}")
            report_text.append("")
            report_text.append("Soru Bazlı Eşleşmeler:")
            for a in analyses:
                report_text.append(f"Soru {a['no']}: {a['outcome'].code} | {a['status']} | {a['score']}/100")
            report_text.append("")
            report_text.append("Ölçülmeyen Çıktılar:")
            if missing:
                for m in missing:
                    report_text.append(f"- {m.code}: {m.text}")
            else:
                report_text.append("- Yok")

            st.download_button(
                "Metin Raporu İndir",
                "\n".join(report_text),
                file_name="tymm_yazili_analiz_raporu.txt",
                mime="text/plain",
            )

        with tab5:
            st.subheader("PDF'den Çıkarılan Metinler")
            c1, c2 = st.columns(2)
            with c1:
                st.text_area("Program Metni", program_text, height=500)
            with c2:
                st.text_area("Yazılı Metni", exam_text, height=500)

else:
    st.info("Sol menüden öğretim programı PDF’i ve yazılı PDF’i yükleyip analizi başlatın.")
