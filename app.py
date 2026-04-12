import streamlit as st
from io import BytesIO
from docxtpl import DocxTemplate
import re
from datetime import datetime, timedelta
import holidays

st.title("TCS Profile Generator")

# Text input
email_text = st.text_area("Paste Candidate Email")

if not email_text.strip():
    st.warning("Please paste candidate email.")
    st.stop()


# -------- Clean Candidate Section --------
if "Full Name" in email_text:
    email_text = email_text.split("Full Name", 1)[1]
    email_text = "Full Name " + email_text


# -------- Parse Fields --------
def parse_fields(text):
    data = {}
    parts = re.split(r'\s*(?=[A-Za-z][A-Za-z0-9\s/()]+?\s*:)', text)

    for part in parts:
        if ":" in part:
            key, value = part.split(":", 1)
            data[key.strip().lower()] = value.strip()

    return data


if st.button("Generate TCS Profile"):

    data = parse_fields(email_text)

    name = data.get("full name (as per aadhar)", " ")
    phone = data.get("contact number", " ")
    email = data.get("email id", " ")
    location = data.get("current location", " ")
    pref_location = data.get("preferred location", " ")
    notice = data.get("notice period", " ")
    reason = data.get("reason for change", " ")
    skills = data.get("skill set", " ")
    exp = data.get("relevant experience", " ")

    # Remove brackets from name
    name = re.sub(r"\(.*?\)", "", name).strip()

    # -------- Skill List --------
    skill_list = [s.strip() for s in re.split(r",|/|;", skills) if s.strip()]

    while len(skill_list) < 3:
        skill_list.append(" ")

    # -------- Date Logic --------
    now = datetime.now()
    india_holidays = holidays.India(years=[now.year, now.year + 1])

    dates = []
    current = now
    hour = now.hour

    if current.weekday() < 5 and current.date() not in india_holidays.keys():

        if hour < 10:
            dates.append(current.strftime("%d-%b-%Y"))
            time1 = "10:00AM-06:00PM"

        elif hour < 14:
            dates.append(current.strftime("%d-%b-%Y"))
            time1 = "02:00PM-06:00PM"

        else:
            current += timedelta(days=1)
            time1 = "10:00AM-06:00PM"

    else:
        current += timedelta(days=1)
        time1 = "10:00AM-06:00PM"

    while len(dates) < 3:

        if current.weekday() >= 5 or current.date() in india_holidays.keys():
            current += timedelta(days=1)
            continue

        dates.append(current.strftime("%d-%b-%Y"))
        current += timedelta(days=1)

    # -------- Load Template --------
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

        "NOTICE_PERIOD": notice if notice.strip() else "Immediate",
        "OFFER": "No",
        "RELOCATION": pref_location if pref_location.strip() else location,
        "REASON": reason if reason else "Career Growth",

        "NEXT_DATE1": dates[0],
        "NEXT_DATE2": dates[1],
        "NEXT_DATE3": dates[2],

        "TIME": time1
    }

    doc.render(context)

    # -------- File Name --------
    mmdd = now.strftime("%m%d")
    clean = re.sub(r'[^A-Za-z0-9]', '', name)

    if not clean:
        clean = "Profile"

    file_name = f"PTN_IN_RGSID_{clean}{mmdd}.docx"

    # -------- Save In Memory --------
    file_stream = BytesIO()
    doc.save(file_stream)

    st.download_button(
        label="Download TCS Profile",
        data=file_stream.getvalue(),
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
