import streamlit as st
import re

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


st.set_page_config(
    page_title="TYMM Yazılı Geliştirme Asistanı",
    page_icon="📝",
    layout="wide"
)

st.title("📝 TYMM Yazılı Geliştirme Asistanı V2")
st.caption("PDF + öğretmen kontrollü hibrit değerlendirme sistemi")


# --------------------------------------------------
# PDF OKUMA
# --------------------------------------------------

def pdf_to_text(uploaded_file):
    if fitz is None:
        st.error("PyMuPDF yüklü değil. requirements.txt dosyasına pymupdf ekleyin.")
        return ""

    text = ""

    pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")

    for page in pdf:
        text += page.get_text("text") + "\n"

    return text


# --------------------------------------------------
# ANA SORULARI AYIRMA
# --------------------------------------------------

def split_main_questions(text, expected_count):

    pattern = r"(?m)^\s*(?:Soru\s*)?(\d{1,2})[\.\)]\s+"

    matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))

    if not matches:
        return []

    question_blocks = []

    for i, match in enumerate(matches):

        start = match.start()

        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        block = text[start:end].strip()

        question_blocks.append(block)

    if len(question_blocks) > expected_count:

        fixed = question_blocks[:expected_count]

        extra = question_blocks[expected_count:]

        fixed[-1] += "\n\n" + "\n\n".join(extra)

        question_blocks = fixed

    return question_blocks


# --------------------------------------------------
# AKILLI SÜREÇ BİLEŞENİ EŞLEŞTİRME
# --------------------------------------------------

PROCESS_MAP = {

    "karşılaştırma": [
        "karşılaştır",
        "fark",
        "benzer",
        "ortak"
    ],

    "neden-sonuç": [
        "neden",
        "sonuç",
        "açıklay",
        "gerekçe",
        "ilişki",
        "etki"
    ],

    "grafik yorumlama": [
        "grafik",
        "çiz",
        "yorum",
        "eğri",
        "değişim"
    ],

    "tablo yorumlama": [
        "tablo",
        "veri",
        "inceley",
        "analiz"
    ],

    "yorumlama": [
        "yorum",
        "değerlendir",
        "açıklay"
    ]
}


# --------------------------------------------------
# ANALİZ
# --------------------------------------------------

def analyze_process_components(question_text, teacher_components):

    components = [
        c.strip()
        for c in re.split(r",|\n|;", teacher_components)
        if c.strip()
    ]

    reached = []

    not_reached = []

    q = question_text.lower()

    for component in components:

        component_lower = component.lower()

        matched = False

        for key, keywords in PROCESS_MAP.items():

            if key in component_lower:

                for kw in keywords:

                    if kw in q:
                        matched = True
                        break

            if matched:
                break

        if component_lower in q:
            matched = True

        if matched:
            reached.append(component)
        else:
            not_reached.append(component)

    return components, reached, not_reached


def generate_feedback(reached, not_reached):

    total = len(reached) + len(not_reached)

    if total == 0:

        level = "Süreç bileşeni girilmediği için değerlendirme yapılamadı."

    elif len(reached) == 0:

        level = "Soru TYMM yaklaşımına kısmen uygundur ancak süreç bileşenleri daha görünür hale getirilebilir."

    elif len(reached) < total:

        level = "Soru birçok TYMM süreç bileşenini desteklemektedir. Bazı süreç boyutları daha görünür hale getirilebilir."

    else:

        level = "Soru TYMM süreç bileşenlerini güçlü biçimde desteklemektedir."

    if len(not_reached) == 0:

        suggestion = "Soru güçlü yapıdadır. Rubrik ve cevap anahtarı ile desteklenmesi önerilir."

    else:

        suggestion = (
            "Şu süreç bileşenlerini güçlendirecek kısa yönlendirmeler eklenebilir: "
            + ", ".join(not_reached)
        )

    return level, suggestion


# --------------------------------------------------
# ÖĞRETMEN PLANI
# --------------------------------------------------

st.header("1. Yazılı Planı")

question_count = st.number_input(
    "Ana soru sayısı",
    min_value=1,
    max_value=20,
    value=10
)

plans = []

for i in range(1, question_count + 1):

    with st.expander(f"{i}. Ana Soru", expanded=False):

        outcome = st.text_area(
            f"{i}. soru öğrenme çıktısı",
            key=f"outcome_{i}"
        )

        components = st.text_area(
            f"{i}. soru TYMM süreç bileşenleri",
            placeholder="Örnek: neden-sonuç ilişkisi, grafik yorumlama",
            key=f"component_{i}"
        )

        plans.append({
            "outcome": outcome,
            "components": components
        })


# --------------------------------------------------
# PDF
# --------------------------------------------------

st.header("2. Yazılı PDF")

uploaded_pdf = st.file_uploader(
    "PDF yükleyiniz",
    type=["pdf"]
)


if uploaded_pdf:

    raw_text = pdf_to_text(uploaded_pdf)

    st.success("PDF başarıyla okundu")

    with st.expander("Ham PDF Metni"):
        st.text_area(
            "PDF içeriği",
            raw_text,
            height=300
        )

    question_blocks = split_main_questions(
        raw_text,
        question_count
    )

    if len(question_blocks) == 0:

        st.warning(
            "Ana soru ayrıştırılamadı. Manuel giriş yapabilirsiniz."
        )

        question_blocks = [""] * question_count

    if len(question_blocks) < question_count:

        missing = question_count - len(question_blocks)

        question_blocks += [""] * missing

    st.header("3. Ana Soru Kontrolü")

    st.info(
        "Alt maddeler aynı ana soru içinde kalmalıdır."
    )

    edited_questions = []

    for i in range(question_count):

        edited = st.text_area(
            f"{i+1}. Ana Soru Metni",
            value=question_blocks[i],
            height=250,
            key=f"question_edit_{i}"
        )

        edited_questions.append(edited)

    st.header("4. TYMM Analizi")

    if st.button("Yazılıyı Analiz Et"):

        for i in range(question_count):

            plan = plans[i]

            question = edited_questions[i]

            components, reached, not_reached = analyze_process_components(
                question,
                plan["components"]
            )

            level, suggestion = generate_feedback(
                reached,
                not_reached
            )

            with st.expander(f"{i+1}. Soru Analizi", expanded=True):

                st.markdown("### Öğrenme Çıktısı")
                st.write(plan["outcome"])

                st.markdown("### Süreç Bileşenleri")
                st.write(
                    ", ".join(components) if components else "Girilmedi"
                )

                st.markdown("### Ulaşılan Süreç Bileşenleri")
                st.success(
                    ", ".join(reached)
                    if reached else
                    "Açık biçimde tespit edilemedi"
                )

                st.markdown("### Güçlendirilebilecek Süreç Bileşenleri")
                st.warning(
                    ", ".join(not_reached)
                    if not_reached else
                    "Yok"
                )

                if len(components) > 0:

                    st.metric(
                        "Karşılama Düzeyi",
                        f"{len(reached)}/{len(components)}"
                    )

                st.markdown("### Genel Değerlendirme")
                st.info(level)

                st.markdown("### Geliştirme Önerisi")
                st.success(suggestion)


st.markdown("---")
st.caption("TYMM Yazılı Geliştirme Asistanı V2")
