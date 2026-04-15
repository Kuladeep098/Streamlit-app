import streamlit as st
from docxtpl import DocxTemplate
import re
from datetime import datetime, timedelta
import holidays

st.title("TCS Profile Generator")

email_text = st.text_area("Paste Candidate Email")

email_text = clean_email(email_text)

if not email_text.strip():
    st.warning("Please paste candidate email.")
    st.stop()

def clean_email(text):
    stop_words = [
    "Warm Regards",
    "Thanks & Regards",
    "Best Regards",
    "Regards",
    "Kind Regards",
]
    for word in stop_words:
        if word in text:
            text = text.split(word)[0]
    return text

# SAFE FIELD EXTRACTION
def extract(field, text):
    match = re.search(rf"^{field}\s*:\s*(.*)", text, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else ""


if st.button("Generate TCS Profile"):

    name = extract(r"Full Name \(As per Aadhar\)", email_text)
    phone = extract("Contact Number", email_text)
    phone = re.findall(r"\d{10}", phone)
    phone = phone[0] if phone else ""
    email = extract("Email ID", email_text)
    location = extract("Current Location", email_text)
    pref_location = extract("Preferred Location", email_text)
    notice = extract("Notice Period", email_text)
    reason = extract("Reason for Change", email_text)
    reason = reason.split(":")[0] if reason else ""

    skills = extract("Skill Set", email_text)


    if skills:
        skill_list = [s.strip() for s in re.split(r",|/|;", skills) if s.strip()]
    else:
        skill_list = []

    while len(skill_list) < 3:
        skill_list.append(" ")

    exp = extract("Relevant Experience", email_text)
    if not exp:
        exp = extract("Total Experience", email_text)

    now = datetime.now()
    india_holidays = holidays.India(years=now.year)

    dates = []
    current = now
    hour = now.hour


    if current.weekday() < 5 and current.date() not in india_holidays:

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

        if current.weekday() >= 5 or current.date() in india_holidays:
            current += timedelta(days=1)
            continue

        dates.append(current.strftime("%d-%b-%Y"))
        current += timedelta(days=1)


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

        "NOTICE_PERIOD": notice if notice else "Immediate",
        "OFFER": "No",
        "RELOCATION": pref_location if pref_location else location,
        "REASON": reason if reason else "Career Growth",

        "NEXT_DATE1": dates[0],
        "NEXT_DATE2": dates[1],
        "NEXT_DATE3": dates[2],

        "TIME": time1,
    }

    doc.render(context)

    mmdd = now.strftime("%m%d")
    clean = re.sub(r'[^A-Za-z0-9]', '', name)

    if not clean:
        clean = "Profile"

    file_name = f"PTN_IN_RGSID_{clean}{mmdd}.docx"

    doc.save(file_name)

    with open(file_name, "rb") as file:
        st.download_button(
            label="Download TCS Profile",
            data=file,
            file_name=file_name
        )
