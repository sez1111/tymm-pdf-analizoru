
import re
from dataclasses import dataclass
from typing import List, Dict
from collections import Counter
import streamlit as st
import fitz

APP_VERSION = "v11 - SADE SÜREÇ GİRİŞİ / ÖĞRETMEN PLANLI ANALİZ"

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

def read_pdf(file) -> str:
    data = file.read()
    doc = fitz.open(stream=data, filetype="pdf")
    return "\n".join([p.get_text("text") for p in doc])

def detect_subparts(q_text: str) -> List[str]:
    t = re.sub(r"\s+([a-eA-E])[\)\.]\s+", r"\n\1) ", q_text)
    matches = list(re.finditer(r"(?:^|\n)\s*([a-eA-E])[\)\.]\s+", t))
    if not matches:
        return []
    parts = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i+1].start() if i+1 < len(matches) else len(t)
        body = t[start:end].strip()
        if body:
            parts.append(f"{m.group(1).lower()}) {body}")
    return parts

def split_questions(text: str, expected_count: int = None) -> List[Question]:
    t = text.replace("\r", "\n")
    t = re.sub(r"[ \t]+", " ", t)

    patterns = [
        r"(?i)\bSoru\s*(\d{1,2})\s*[:\.\-–)]\s*",
        r"(?<![\d])\b(\d{1,2})\s*[\.\)]\s+(?=[A-Za-zÇĞİÖŞÜçğıöşü])",
        r"(?<![\d])\b(\d{1,2})\s*[-–]\s+(?=[A-Za-zÇĞİÖŞÜçğıöşü])",
    ]

    normalized = t
    for pat in patterns:
        normalized = re.sub(pat, lambda m: f"\n{int(m.group(1))}. ", normalized)

    matches = list(re.finditer(r"(?:^|\n)\s*(\d{1,2})[\.\)]\s+", normalized))
    if expected_count:
        matches = [m for m in matches if 1 <= int(m.group(1)) <= expected_count]

    if not matches:
        clean = normalized.strip()
        return [Question(1, clean, detect_subparts(clean))] if clean else []

    questions = []
    for i, m in enumerate(matches):
        q_no = int(m.group(1))
        start = m.end()
        end = matches[i+1].start() if i+1 < len(matches) else len(normalized)
        body = normalized[start:end].strip()
        if len(re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]", body)) < 8:
            continue
        existing = next((q for q in questions if q.no == q_no), None)
        if existing:
            existing.text += "\n" + body
            existing.subparts = detect_subparts(existing.text)
        else:
            questions.append(Question(q_no, body, detect_subparts(body)))

    if expected_count and len(questions) == 1 and expected_count > 1:
        soft = re.sub(r"(?<![\d])\b(\d{1,2})[\.\)]\s+", lambda m: f"\n{int(m.group(1))}. ", t)
        soft_matches = list(re.finditer(r"(?:^|\n)\s*(\d{1,2})[\.\)]\s+", soft))
        soft_matches = [m for m in soft_matches if 1 <= int(m.group(1)) <= expected_count]
        if len(soft_matches) > 1:
            qs = []
            for i, m in enumerate(soft_matches):
                q_no = int(m.group(1))
                start = m.end()
                end = soft_matches[i+1].start() if i+1 < len(soft_matches) else len(soft)
                body = soft[start:end].strip()
                if len(re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]", body)) >= 8:
                    qs.append(Question(q_no, body, detect_subparts(body)))
            if qs:
                questions = qs

    return sorted(questions, key=lambda x: x.no)

PROCESS_ALIASES = {
    "açıklama": ["açıkla", "açıklayınız", "ifade", "yazınız", "tanımla", "belirtiniz"],
    "karşılaştırma": ["karşılaştır", "fark", "benzer", "kıyas"],
    "yorumlama": ["yorum", "grafik", "tablo", "veri", "inceleyiniz"],
    "çıkarım yapma": ["çıkarım", "sonuç çıkar", "ulaşılır", "etkisini açıklayınız"],
    "çıkarım": ["çıkarım", "sonuç çıkar", "ulaşılır", "etkisini açıklayınız"],
    "gerekçelendirme": ["gerekçe", "gerekçelendir", "kanıt", "neden"],
    "sorgulama": ["sorgula", "nasıl", "neden", "hangi değişken"],
    "sınıflandırma": ["sınıflandır", "çeşit", "tür", "grup"],
    "değerlendirme": ["değerlendir", "uygun", "hangisi", "karar", "tercih"],
    "neden-sonuç kurma": ["neden-sonuç", "neden sonuç", "etki", "sonuç", "mekanizma"],
    "neden-sonuç": ["neden-sonuç", "neden sonuç", "etki", "sonuç", "mekanizma"],
    "analiz": ["analiz", "incele", "yorumla", "mekanizma", "ilişki"],
    "ilişkilendirme": ["ilişkilendir", "arasındaki ilişki", "ilişkisini"],
    "modelleme": ["model", "şema", "grafiği çiz", "çiziniz"],
    "deney tasarlama": ["deney", "hipotez", "değişken", "kontrollü deney"],
}

def split_processes(raw: str) -> List[str]:
    parts = [p.strip().lower() for p in re.split(r",|;|\n", raw or "") if p.strip()]
    clean = []
    for p in parts:
        if p not in clean:
            clean.append(p)
    return clean

def match_process_components(question_text: str, target_processes: List[str]):
    matched = []
    missing = []
    for process in target_processes:
        pn = norm(process)
        aliases = PROCESS_ALIASES.get(pn, [pn])
        direct = any(norm(a) in norm(question_text) for a in aliases)
        if pn == "analiz" and has_any(question_text, ["mekanizma", "ilişki", "yorumlayınız", "inceleyiniz"]):
            direct = True
        if pn == "değerlendirme" and has_any(question_text, ["uygun", "hangisi", "karar", "tercih"]):
            direct = True
        if pn in ["yorumlama", "analiz"] and has_any(question_text, ["grafik", "tablo", "veri"]):
            direct = True
        if direct:
            matched.append(process)
        else:
            missing.append(process)
    return matched, missing

def detect_evidence(t: str) -> List[str]:
    ev = ["Açık uçlu yanıt"]
    if has_any(t, ["tablo", "veri"]):
        ev.append("Tablo/veri analizi")
    if has_any(t, ["grafik", "grafiği çiz"]):
        ev.append("Grafik yorumlama/çizme")
    if has_any(t, ["gerekçe", "gerekçelendir"]):
        ev.append("Gerekçeli açıklama")
    if has_any(t, ["besin zinciri", "besin ağı", "şema"]):
        ev.append("Şema/ağ oluşturma")
    if has_any(t, ["deney", "hipotez", "değişken"]):
        ev.append("Deneysel düşünme")
    return ev

def improvement_suggestion(matched: List[str], missing: List[str], evidence: List[str]) -> str:
    if not missing:
        return "Soru, öğretmenin hedeflediği süreç bileşenlerini güçlü biçimde temsil ediyor. Beklenen cevap ve rubrik eklenirse değerlendirme güvenirliği artar."
    suggestions = []
    if "gerekçelendirme" in missing:
        suggestions.append('Yönergeye “Cevabınızı bilimsel gerekçelerle açıklayınız.” ifadesi eklenebilir.')
    if "değerlendirme" in missing:
        suggestions.append('Öğrenciden iki seçenek/durum arasında karar vermesi ve karar ölçütlerini belirtmesi istenebilir.')
    if "karşılaştırma" in missing:
        suggestions.append('İki durum, süreç veya canlı ilişkisi karşılaştırmalı biçimde sunulabilir.')
    if "çıkarım" in missing or "çıkarım yapma" in missing:
        suggestions.append('Kısa bir veri, grafik veya gözlem sonucu verilerek öğrenciden çıkarım yapması istenebilir.')
    if "yorumlama" in missing or "analiz" in missing:
        suggestions.append('Soruya tablo/grafik/senaryo eklenerek öğrencinin veriyi yorumlaması sağlanabilir.')
    if "deney tasarlama" in missing:
        suggestions.append('Hipotez, bağımlı-bağımsız değişken veya deney düzeneği içeren alt madde eklenebilir.')
    if "modelleme" in missing:
        suggestions.append('Öğrenciden şema, grafik ya da model oluşturması istenebilir.')
    if len(evidence) <= 1:
        suggestions.append("Öğrenme kanıtını güçlendirmek için grafik, tablo, kısa senaryo veya beklenen cevap rubriği eklenebilir.")
    return " ".join(suggestions) if suggestions else "Eksik süreç bileşenlerini görünür kılmak için soru yönergesine daha açık işlem fiilleri eklenebilir."

def quality_level(process_ratio: float) -> str:
    if process_ratio >= 0.75:
        return "🟢 Güçlü"
    if process_ratio >= 0.40:
        return "🟡 Geliştirilebilir"
    return "🔴 Desteklenmeli"

def analyze_question_against_plan(q: Question, plan: Dict):
    target_processes = plan["processes"]
    matched, missing = match_process_components(q.text, target_processes)
    evidence = detect_evidence(q.text)
    total = len(target_processes)
    ratio = len(matched) / total if total else 0
    return {
        "no": q.no,
        "text": q.text,
        "subparts": q.subparts,
        "learning_outcome": plan["learning_outcome"],
        "target_processes": target_processes,
        "matched_processes": matched,
        "missing_processes": missing,
        "process_count": f"{len(matched)}/{total}" if total else "Süreç girilmedi",
        "process_ratio": ratio,
        "evidence": evidence,
        "status": quality_level(ratio) if total else "🔴 Süreç girilmeli",
        "suggestion": improvement_suggestion(matched, missing, evidence) if total else "TYMM kapsamında süreç bileşeni zorunludur. Bu soru için hedef süreç bileşenlerini girin."
    }

def process_density(analyses):
    c = Counter()
    for a in analyses:
        for p in a["matched_processes"]:
            c[p] += 1
    return c

st.set_page_config(page_title="TYMM v11 Sade Süreç Girişi", layout="wide")
st.title("TYMM Yazılı Geliştirme Asistanı")
st.caption(APP_VERSION)

st.info("Bu sürümde “yaygın süreç bileşeni” seçeneği yoktur. Her soru için süreç bileşenlerini öğretmen tek kutuya yazar. Süreç bileşeni zorunludur.")

st.sidebar.header("1. Yazılı Planı")
question_count = st.sidebar.number_input("Yazılıdaki ana soru sayısı", min_value=1, max_value=50, value=10, step=1)

st.sidebar.header("2. Yazılı PDF")
exam_pdf = st.sidebar.file_uploader("Yazılı PDF", type=["pdf"])

st.sidebar.header("3. Analiz")
run = st.sidebar.button("Yazılıyı Planıma Göre Analiz Et", type="primary")

st.subheader("A) Öğretmen Yazılı Planı")
st.caption("Her ana soru için öğrenme çıktısını ve TYMM süreç bileşenlerini yazın. Örnek süreçler: açıklama, yorumlama, gerekçelendirme, çıkarım yapma, değerlendirme, analiz.")

with st.form("planning_form"):
    plan = []
    for i in range(1, int(question_count) + 1):
        with st.expander(f"Soru {i} hedefleri", expanded=(i <= 3)):
            lo = st.text_input(
                f"Soru {i} öğrenme çıktısı / kazanım",
                key=f"lo_{i}",
                placeholder="Örn. BİY.10.2.1 Ekosistemde enerji akışı ve madde döngülerini yorumlayabilme"
            )
            raw_proc = st.text_area(
                f"Soru {i} hedef süreç bileşenleri (zorunlu)",
                key=f"proc_{i}",
                placeholder="Örn. yorumlama, neden-sonuç kurma, çıkarım yapma, değerlendirme",
                height=80
            )
            plan.append({
                "question_no": i,
                "learning_outcome": lo.strip() or f"Soru {i} için öğrenme çıktısı girilmedi",
                "processes": split_processes(raw_proc)
            })
    st.form_submit_button("Planı Kaydet / Güncelle")

missing_process_questions = [p["question_no"] for p in plan if not p["processes"]]
plan_ready_count = sum(1 for p in plan if p["processes"])
st.write(f"**Plan durumu:** {plan_ready_count}/{question_count} soru için süreç bileşeni girildi.")

if missing_process_questions:
    st.warning("Süreç bileşeni girilmeyen sorular var: " + ", ".join(map(str, missing_process_questions)) + ". Analiz için her soru en az bir süreç bileşeni içermeli.")

if run:
    if not exam_pdf:
        st.error("Lütfen yazılı PDF'ini yükleyin.")
    elif missing_process_questions:
        st.error("Analiz başlatılamadı. TYMM kapsamında her soru için süreç bileşeni girilmelidir.")
    else:
        with st.spinner("Yazılı PDF okunuyor ve güçlü soru ayırma ile analiz ediliyor..."):
            exam_text = read_pdf(exam_pdf)
            questions = split_questions(exam_text, expected_count=int(question_count))
            q_map = {q.no: q for q in questions}
            analyses = []
            for p in plan:
                q_no = p["question_no"]
                if q_no in q_map:
                    analyses.append(analyze_question_against_plan(q_map[q_no], p))
                else:
                    analyses.append({
                        "no": q_no, "text": "", "subparts": [],
                        "learning_outcome": p["learning_outcome"],
                        "target_processes": p["processes"],
                        "matched_processes": [],
                        "missing_processes": p["processes"],
                        "process_count": f"0/{len(p['processes'])}",
                        "process_ratio": 0,
                        "evidence": [],
                        "status": "🔴 Desteklenmeli",
                        "suggestion": "Bu ana soru PDF içinde algılanamadı. Soru numaralandırması veya PDF metni kontrol edilebilir."
                    })

            total_target = sum(len(a["target_processes"]) for a in analyses)
            total_matched = sum(len(a["matched_processes"]) for a in analyses)
            process_coverage = total_matched / total_target if total_target else 0
            covered_questions = sum(1 for a in analyses if a["matched_processes"])
            question_coverage = covered_questions / len(analyses) if analyses else 0
            overall = quality_level(process_coverage)
            p_counter = process_density(analyses)

        st.success(f"Analiz tamamlandı. PDF içinde {len(questions)} ana soru algılandı; plan {len(plan)} ana soru üzerinden değerlendirildi.")

        if len(questions) == 1 and question_count > 1:
            st.error("PDF hâlâ tek ana soru gibi algılandı. Bu durumda PDF metin yapısı bozuk olabilir. 'Ana Soru / Alt Madde Kontrolü' sekmesindeki ham metne bakın.")
        elif len(questions) != question_count:
            st.warning(f"Planlanan soru sayısı {question_count}, PDF'de algılanan ana soru sayısı {len(questions)}. Eksik/fazla soru varsa numaralandırmayı kontrol edin.")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Genel Durum", overall)
        c2.metric("PDF'de Algılanan Ana Soru", len(questions))
        c3.metric("Süreç Bileşeni Kapsama", f"%{round(process_coverage*100)}")
        c4.metric("Soru Kapsama", f"%{round(question_coverage*100)}")

        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Soru Bazlı Analiz",
            "Ana Soru / Alt Madde Kontrolü",
            "Süreç Yoğunluğu",
            "Öğretmen Kılavuzu",
            "Metin Raporu"
        ])

        with tab1:
            st.subheader("Soru Bazlı Plan Uyum Analizi")
            rows = []
            for a in analyses:
                rows.append({
                    "Ana Soru": a["no"],
                    "Öğrenme Çıktısı": a["learning_outcome"],
                    "Hedef Süreçler": ", ".join(a["target_processes"]) if a["target_processes"] else "-",
                    "Süreç Eşleşmesi": a["process_count"],
                    "Eşleşen Süreçler": ", ".join(a["matched_processes"]) if a["matched_processes"] else "-",
                    "Desteklenebilecek Süreçler": ", ".join(a["missing_processes"]) if a["missing_processes"] else "-",
                    "Durum": a["status"],
                    "Geliştirme Önerisi": a["suggestion"],
                })
            st.dataframe(rows, use_container_width=True)

            for a in analyses:
                with st.expander(f"Soru {a['no']} — {a['status']} — süreç: {a['process_count']}"):
                    st.write("**Öğrenme çıktısı:**", a["learning_outcome"])
                    st.write("**Hedef süreç bileşenleri:**", ", ".join(a["target_processes"]) if a["target_processes"] else "Girilmedi")
                    st.write("**Soru metni:**")
                    st.write(a["text"] or "PDF içinde bu soru algılanamadı.")
                    if a["subparts"]:
                        st.write("**Algılanan alt maddeler:**")
                        for sp in a["subparts"]:
                            st.write("-", sp[:300])
                    st.write("**Eşleşen süreçler:**", ", ".join(a["matched_processes"]) if a["matched_processes"] else "Yok")
                    st.write("**Desteklenebilecek süreçler:**", ", ".join(a["missing_processes"]) if a["missing_processes"] else "Yok")
                    st.success(a["suggestion"])

        with tab2:
            st.subheader("Ana Soru / Alt Madde Kontrolü")
            st.dataframe([
                {
                    "Ana Soru": q.no,
                    "Alt Madde Sayısı": len(q.subparts),
                    "Alt Maddeler": " | ".join([sp[:120] for sp in q.subparts]) if q.subparts else "-",
                    "Metin Önizleme": q.text[:300]
                }
                for q in questions
            ], use_container_width=True)
            with st.expander("PDF'den çıkan ham metin"):
                st.text_area("Ham metin", exam_text, height=500)

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
            st.subheader("Öğretmen TYMM Kılavuzu")
            guide = []
            for a in analyses:
                guide.append({
                    "Ana Soru": a["no"],
                    "Öğrenme Çıktısı": a["learning_outcome"],
                    "Hedef Süreç Sayısı": len(a["target_processes"]),
                    "Eşleşen Süreç Sayısı": len(a["matched_processes"]),
                    "Eşleşen Süreçler": ", ".join(a["matched_processes"]) if a["matched_processes"] else "-",
                    "Desteklenebilecek Süreçler": ", ".join(a["missing_processes"]) if a["missing_processes"] else "-",
                    "Öğrenme Kanıtı": ", ".join(a["evidence"]) if a["evidence"] else "-",
                    "Geliştirici Not": a["suggestion"]
                })
            st.dataframe(guide, use_container_width=True)

        with tab5:
            report = []
            report.append("TYMM ÖĞRETMEN PLANLI YAZILI GELİŞTİRME RAPORU")
            report.append(f"Uygulama sürümü: {APP_VERSION}")
            report.append(f"Planlanan ana soru sayısı: {question_count}")
            report.append(f"PDF'de algılanan ana soru sayısı: {len(questions)}")
            report.append(f"Genel durum: {overall}")
            report.append(f"Süreç bileşeni kapsama: %{round(process_coverage*100)}")
            report.append("")
            report.append("Soru bazlı analiz:")
            for a in analyses:
                report.append(f"Soru {a['no']}: {a['learning_outcome']} | Süreç: {a['process_count']} | Eşleşen: {', '.join(a['matched_processes']) or '-'} | Desteklenebilecek: {', '.join(a['missing_processes']) or '-'} | Öneri: {a['suggestion']}")
            report_text = "\n".join(report)
            st.text_area("Rapor", report_text, height=420)
            st.download_button("Metin Raporu İndir", report_text, file_name="tymm_ogretmen_planli_rapor.txt")
