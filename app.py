import streamlit as st
from docxtpl import DocxTemplate
import re
from datetime import datetime, timedelta
import holidays

st.title("TCS Profile Generator")

email_text = st.text_area("Paste Candidate Email")

def extract(field, text):
    matches = re.findall(field + r".*?:\s*(.*)", text, re.IGNORECASE)
    return matches[-1].strip() if matches else ""

if st.button("Generate TCS Profile"):

    name = extract("Full Name", email_text)
    phone = extract("Contact Number", email_text)
    email = extract("Email ID", email_text)
    location = extract("Current Location", email_text)
    notice = extract("Notice Period", email_text)
    reason = extract("Reason for Change", email_text)

    skills = extract("Skill Set", email_text)
    skill_list = [s.strip() for s in re.split(r",|/|;", skills)]

    while len(skill_list) < 3:
        skill_list.append("")

    exp = extract("Relevant Experience", email_text)

    now = datetime.now()
    india_holidays = holidays.India(years=now.year)

    dates = []
    current = now

    while len(dates) < 3:
        current += timedelta(days=1)

        if current.weekday() >= 5:
            continue

        if current.date() in india_holidays:
            continue

        dates.append(current.strftime("%d-%b-%Y"))

    hour = now.hour

    if hour < 10:
        time_slot = "10:00AM-06:00PM"
    elif hour < 14:
        time_slot = "02:00PM-06:00PM"
    else:
        time_slot = "10:00AM-06:00PM"

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

        "NOTICE_PERIOD": notice,
        "OFFER": "No",
        "RELOCATION": location,
        "REASON": reason,

        "NEXT_DATE1": dates[0],
        "NEXT_DATE2": dates[1],
        "NEXT_DATE3": dates[2],

        "TIME": time_slot
    }

    doc.render(context)

    mmdd = now.strftime("%m%d")
    clean = name.replace(" ", "")

    file_name = f"PTN_IN_RGSID_{clean}{mmdd}.docx"

    doc.save(file_name)

    with open(file_name, "rb") as file:
        st.download_button(
            label="Download TCS Profile",
            data=file,
            file_name=file_name
        )
