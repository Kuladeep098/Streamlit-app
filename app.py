import streamlit as st
from docxtpl import DocxTemplate
import re
from datetime import datetime, timedelta
import holidays
from dateutil import parser
import pytz

# ================= UI =================
st.title("📄 TCS Profile Generator")

email_text = st.text_area("Paste Candidate Email / Naukri / Resdex Data", height=300)

tracker_format = st.text_input(
    "Paste Tracker Columns (TAB separated)",
    placeholder="Dates\tBeeline ID\tCandidate Name\tContact Number\tEmail ID\tSkill\tTotal Exp"
)

# ================= CLEAN =================
def clean(x):
    """Collapses ALL whitespace (including newlines) into single spaces.
    Use this only on values where line breaks carry no meaning."""
    return re.sub(r"\s+", " ", x).strip() if x else ""

def soft_clean(x):
    """Collapses horizontal whitespace (spaces/tabs) but PRESERVES newlines.
    Use this for any field (like Key Skills) where each line is a separate item -
    calling clean() on it before splitting destroys the line breaks the split relies on."""
    if not x:
        return ""
    x = x.strip()
    x = re.sub(r"[ \t]+", " ", x)
    return x

# ================= BEST MATCH =================
def get_best_match(pattern, text):
    matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)

    for m in matches:
        if isinstance(m, tuple):
            m = m[0]

        value = m.strip()
        if value and value.lower() not in ["na", "n/a", "-", ""]:
            return value
    return ""

# ================= REGEX =================
def smart_extract(text):

    name = clean(get_best_match(
        r"Full Name\s*\(As per Aadhar\)\s*:\s*(.*?)\s*(?=Contact Number)", text
    ))

    phone = get_best_match(r"Contact Number\s*:\s*(\d{10})", text)

    email = clean(get_best_match(
        r"Email ID\s*:\s*([\w\.-]+@[\w\.-]+)", text
    ))

    dob_raw = clean(get_best_match(
        r"Date of Birth\s*:\s*([0-9/\- ]{8,15})", text
    ))

    location = clean(get_best_match(
        r"Current Location\s*:\s*(.*?)\s*(?=Preferred Location|Compliance|$)", text
    ))

    pref_location = clean(get_best_match(
        r"Preferred Location\s*:\s*(.*?)\s*(?=Compliance|$)", text
    ))

    # FIX: use soft_clean so individual skills (newline separated) survive to the split step
    skills = soft_clean(get_best_match(
        r"Skill Set\s*:\s*(.*?)\s*(Total Experience|Relevant Experience)", text
    ))

    exp = clean(get_best_match(
        r"Relevant Experience\s*:\s*([0-9\+\s]*(?:Years|Year|yrs|yr))", text
    ))

    return {
        "Full Name": name,
        "Contact Number": phone,
        "Email ID": email,
        "Current Location": location,
        "Preferred Location": pref_location,
        "Skills": skills,
        "Experience": exp,
        "Date of Birth": dob_raw,
    }

# ================= NAUKRI / RESDEX EXTRACT =================
def first_phone(text):
    m = re.search(r"(?<!\d)(?:\+91[\s\-]?)?([6-9]\d{9})(?!\d)", text)
    return m.group(1) if m else ""

def first_email(text):
    m = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    return m.group(0) if m else ""

def name_from_lines(text):
    ignore = [
        "naukri", "resdex", "profile", "candidate", "contact", "email",
        "phone", "mobile", "location", "experience", "skills", "key skills",
        "education", "employment", "attached cv", "verified", "active",
        "modified", "save", "forward", "schedule", "notice", "summary",
        "may also know", "work experience", "current location",
        "preferred location"
    ]

    lines = [clean(x) for x in text.splitlines() if clean(x)]

    for line in lines[:40]:
        low = line.lower()

        if any(word in low for word in ignore):
            continue

        if "@" in line or re.search(r"\d{5,}", line):
            continue

        if re.fullmatch(r"[A-Za-z][A-Za-z .']{2,70}", line):
            words = line.split()
            if 2 <= len(words) <= 5:
                return line.title()

    return ""

def naukri_extract(text):

    name = clean(get_best_match(
        r"(?:Candidate Name|Full Name|Name)\s*[:\-]\s*([A-Za-z][A-Za-z .']{2,80})",
        text
    ))

    if not name:
        name = name_from_lines(text)

    phone = first_phone(text)
    email = first_email(text)

    location = clean(get_best_match(
        r"(?:Current Location|Current\s*Location|Location)\s*[:\-]?\s*([^\n\r]+)",
        text
    ))

    pref_location = clean(get_best_match(
        r"(?:Preferred Location|Preferred\s*Work\s*Location|Pref\.?\s*Location)\s*[:\-]?\s*([^\n\r]+)",
        text
    ))

    # fallback city detection
    if not location:
        location = clean(get_best_match(
            r"\b(Bengaluru|Bangalore|Hyderabad|Chennai|Pune|Mumbai|Delhi|Noida|Gurgaon|Gurugram|Kolkata|Remote)\b",
            text
        ))

    # FIX (bug #1): was clean(...) -> destroyed the newlines that separate each
    # skill in a "Key skills" block, so the whole block became a single skill.
    # soft_clean() keeps line breaks intact so the later split on "\n" actually works.
    skills_raw = soft_clean(get_best_match(
        r"(?:Key Skills|Keyskills|Skill Set|Skills)\s*[:\-]?\s*(.*?)\s*(?=May also know|Work Summary|Profile Summary|Employment|Education|Activity|Attached CV|Notice|Preferred Location|Current Location|$)",
        text
    ))

    if not skills_raw:
        skills_raw = soft_clean(get_best_match(
            r"(?:May also know)\s*[:\-]?\s*(.*?)\s*(?=Work Summary|Profile Summary|Employment|Education|Activity|Attached CV|$)",
            text
        ))

    # ---- Experience: try labeled "Total Experience"/"Experience" value first ----
    exp = clean(get_best_match(
        r"(?:Total Experience|Total Exp|Experience)\s*[:\-]?\s*([0-9]{1,2}(?:\.[0-9]{1,2})?\+?\s*(?:Years?|Yrs?|Yr)(?:\s*[0-9]{1,2}\s*(?:Months?|Mos?|M))?)",
        text
    ))

    # FIX (bug #2, new): Naukri/Resdex profiles show total experience in a compact
    # "5y 10m" form near the top (no "Years"/"Yr" word at all), before any CTC figure.
    # Catch that explicitly, before falling back to the loose generic pattern below.
    if not exp:
        exp = clean(get_best_match(
            r"\b([0-9]{1,2}\s*y\s*[0-9]{1,2}\s*m)\b",
            text
        ))

    # FIX (bug #2): original fallback pattern had no decimal support, so on text like
    # "5.1 years" it matched starting *after* the decimal point ("1 years"), silently
    # dropping the "5". The (?<!\.) lookbehind stops it from starting a match right
    # after a decimal point.
    if not exp:
        exp = clean(get_best_match(
            r"(?<!\.)\b([0-9]{1,2}\+?\s*(?:Years?|Yrs?|Yr))\b",
            text
        ))

    dob_raw = clean(get_best_match(
        r"(?:Date of Birth|DOB|D\.O\.B)\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
        text
    ))

    return {
        "Full Name": name,
        "Contact Number": phone,
        "Email ID": email,
        "Current Location": location,
        "Preferred Location": pref_location,
        "Skills": skills_raw,
        "Experience": exp,
        "Date of Birth": dob_raw,
    }

# ================= AUTO EXTRACT =================
def auto_extract(text):
    normal_data = smart_extract(text)
    naukri_data = naukri_extract(text)

    final = {}

    fields = [
        "Full Name",
        "Contact Number",
        "Email ID",
        "Current Location",
        "Preferred Location",
        "Skills",
        "Experience",
        "Date of Birth",
    ]

    for key in fields:
        final[key] = normal_data.get(key) or naukri_data.get(key) or ""

    return final

# Naukri/Resdex UI artifacts that sometimes get swept into the skills block
# (e.g. a "View IT skills" link sitting right after the last real skill line).
NOISE_SKILLS = {"view it skills", "view more", "show more", "view all", "view it skill"}

# ================= BUTTON =================
if st.button("Generate TCS Profile"):

    if not email_text.strip():
        st.warning("Please paste email / Naukri / Resdex data")
        st.stop()

    data = auto_extract(email_text)

    # ================= CLEAN =================
    name = clean(data.get("Full Name", ""))

    phone_match = re.search(r"\d{10}", data.get("Contact Number", ""))
    phone = phone_match.group() if phone_match else ""

    email = clean(data.get("Email ID", ""))
    location = clean(data.get("Current Location", ""))
    pref_location = clean(data.get("Preferred Location", ""))
    exp = clean(data.get("Experience", ""))

    # ================= DOB =================
    dob_raw = clean(data.get("Date of Birth", ""))
    dob_match = re.search(r"\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}", dob_raw)
    dob = dob_match.group() if dob_match else ""

    mmdd = ""
    if dob:
        try:
            mmdd = parser.parse(dob, dayfirst=True).strftime("%m%d")
        except:
            pass

    # ================= SKILLS =================
    # FIX: skills_raw now still has its newlines (see soft_clean above), so this
    # split actually separates the individual skills instead of returning one blob.
    skills_raw = data.get("Skills", "")
    skill_list = [s.strip().title() for s in re.split(r",|/|\n|;", skills_raw) if s.strip()]
    skill_list = [s for s in skill_list if s.lower() not in NOISE_SKILLS]

    while len(skill_list) < 3:
        skill_list.append(" ")

    # only first 3 skills
    skill_list = skill_list[:3]

    # ================= DATE LOGIC =================
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    india_holidays = holidays.India(years=now.year)

    dates = []

    current = now.replace(hour=0, minute=0, second=0, microsecond=0)

    cutoff = now.replace(hour=14, minute=0, second=0, microsecond=0)

    if now > cutoff:
        current += timedelta(days=1)

    while len(dates) < 3:
        if current.weekday() < 5 and current.date() not in india_holidays:
            dates.append(current.strftime("%d-%b-%Y"))
        current += timedelta(days=1)

    time1 = "10:00AM-06:00PM"

    # ================= DOCX =================
    doc = DocxTemplate("tcs_template.docx")

    context = {
        "NAME": name,
        "CONTACT_NUMBER": phone,
        "EMAIL_ID": email,
        "CURRENT_LOCATION": location,

        "SKILL1": skill_list[0],
        "SKILL2": skill_list[1],
        "SKILL3": skill_list[2],

        "EXP1": exp,
        "EXP2": exp,
        "EXP3": exp,

        "NOTICE_PERIOD": "Immediate",
        "OFFER": "No",
        "RELOCATION": pref_location if pref_location else location,
        "REASON": "Career Growth",

        "NEXT_DATE1": dates[0],
        "NEXT_DATE2": dates[1],
        "NEXT_DATE3": dates[2],
        "TIME": time1,
    }

    doc.render(context)

    file_name = f"PTN_IN_RGSID_{re.sub(r'[^A-Za-z0-9]', '', name)}{mmdd}.docx"
    doc.save(file_name)

    with open(file_name, "rb") as f:
        st.download_button("Download TCS Profile", f, file_name)

    st.success("✅ Profile Generated Successfully")

    # ================= TRACKER =================
    if tracker_format:

        tracker_cols = tracker_format.split("\t")

        def get_value(col):
            col = col.lower().strip()

            if "name" in col:
                return name
            elif "contact" in col or "phone" in col:
                return phone
            elif "email" in col:
                return email
            elif "skill" in col:
                return ", ".join(skill_list)
            elif "total exp" in col:
                return exp
            elif "rel exp" in col:
                return exp
            elif "current location" in col:
                return location
            elif "pref" in col:
                return pref_location
            elif "dob" in col or "birth" in col:
                return dob
            elif "date" in col:
                return datetime.now().strftime("%d-%m-%Y")
            else:
                return ""

        row = [get_value(c) for c in tracker_cols]
        tracker_line = "\t".join(row)

        st.subheader("📊 Tracker Output (Copy Paste)")
        st.code(tracker_line)
