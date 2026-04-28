import streamlit as st
from google import genai
from docxtpl import DocxTemplate
import json, re
from datetime import datetime, timedelta
import holidays
from dateutil import parser
import os

# ================= UI =================
st.title("📄 TCS Profile Generator (AI + Smart Parsing)")

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

    # ---------- Try Gemini ----------
    try:
        os.environ["GOOGLE_API_KEY"] = st.secrets.get("GOOGLE_API_KEY", "")

        client = genai.Client()

        prompt = f"""
        Extract details and return ONLY JSON.

        {{
          "Full Name": "",
          "Contact Number": "",
          "Email ID": "",
          "Current Location": "",
          "Preferred Location": "",
          "Skills": "",
          "Experience": "",
          "Date of Birth": ""
        }}

        Email:
        {email_text}
        """

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )

        text = response.text.strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)

        if match:
            data = json.loads(match.group())
        else:
            data = smart_extract(email_text)

    except:
        st.warning("AI not available → using smart extraction")
        data = smart_extract(email_text)

    # ================= CLEAN =================
    name = clean(data.get("Full Name", ""))
    phone = re.search(r"\d{10}", data.get("Contact Number", ""))
    phone = phone.group() if phone else ""

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

    # ================= DATES =================
    now = datetime.now()
    india_holidays = holidays.India(years=now.year)

    dates = []
    current = now

    if current.hour >= 14:
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
