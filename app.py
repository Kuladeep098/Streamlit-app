import streamlit as st
from docxtpl import DocxTemplate
import re
from datetime import datetime, timedelta
import holidays
from dateutil import parser
import pytz

# ================= UI =================
st.title("📄 TCS Profile Generator")

email_text = st.text_area("Paste Candidate Email", height=300)

# ================= CLEAN =================
def clean(x):
    return re.sub(r"\s+", " ", x).strip() if x else ""

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

    skills = clean(get_best_match(
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

# ================= BUTTON =================
if st.button("Generate TCS Profile"):

    if not email_text.strip():
        st.warning("Please paste email")
        st.stop()

    data = smart_extract(email_text)

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
    dob_match = re.search(r"\d{2}[/\-]\d{2}[/\-]\d{4}", dob_raw)
    dob = dob_match.group() if dob_match else ""

    mmdd = ""
    if dob:
        try:
            mmdd = parser.parse(dob, dayfirst=True).strftime("%m%d")
        except:
            pass

    # ================= SKILLS =================
    skills_raw = data.get("Skills", "")
    skill_list = [s.strip().title() for s in re.split(r",|/|\n|;", skills_raw) if s.strip()]

    while len(skill_list) < 3:
        skill_list.append(" ")

    # ================= DATE LOGIC (FINAL FIX) =================
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    india_holidays = holidays.India(years=now.year)

    # DEBUG (optional)
    st.write("Current IST Time:", now.strftime("%d-%b-%Y %I:%M %p"))

    dates = []

    # Reset to start of day
    current = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Cutoff time 2 PM
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
