import streamlit as st
from docxtpl import DocxTemplate
import re
from datetime import datetime, timedelta
import holidays
from dateutil import parser

st.title("TCS Profile Generator")

email_text = st.text_area("Paste Candidate Email")

if not email_text.strip():
    st.warning("Please paste candidate email.")
    st.stop()


# CLEAN EMAIL
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


email_text = clean_email(email_text)

# REMOVE HIDDEN CHARACTERS
email_text = email_text.replace("​", "")
email_text = email_text.replace("", "")


# SPLIT PROFESSIONAL AND CANDIDATE SECTIONS
parts = re.split(r"Candidate\s*Details\s*:", email_text, flags=re.IGNORECASE)

professional_text = parts[0]
candidate_text = parts[1] if len(parts) > 1 else email_text


# SAFE FIELD EXTRACTION
def extract(field, text):
    pattern = rf"{field}\s*[:\-]\s*(.+)"
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else ""


if st.button("Generate TCS Profile"):

    # CANDIDATE DETAILS
    name = extract(r"Full Name \(As per Aadhar\)", candidate_text)

    phone = extract("Contact Number", candidate_text)
    phone_match = re.search(r"\d{10}", phone)
    phone = phone_match.group() if phone_match else ""

    email = extract("Email ID", candidate_text)

    dob = extract("Date of Birth", candidate_text)


    # PROFESSIONAL DETAILS
    location = extract("Current Location", professional_text)

    pref_location = extract("Preferred Location|Peferred Location", professional_text)

    notice = extract("Notice Period", professional_text)

    skills = extract("Skill Set", professional_text)


    # SKILL PROCESSING
    if skills:
        skill_list = [s.strip() for s in re.split(r",|/|;", skills) if s.strip()]
    else:
        skill_list = []

    while len(skill_list) < 3:
        skill_list.append(" ")


    # EXPERIENCE
    exp = extract("Relevant Experience", professional_text)
    if not exp:
        exp = extract("Total Experience", professional_text)


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


    # LOAD TEMPLATE
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
        "REASON": "Career Growth",

        "NEXT_DATE1": dates[0],
        "NEXT_DATE2": dates[1],
        "NEXT_DATE3": dates[2],

        "TIME": time1,
    }

    doc.render(context)


    # DOB → MMDD
    mmdd = ""

    if dob:
        try:
            date_obj = parser.parse(dob)
            mmdd = date_obj.strftime("%m%d")
        except:
            mmdd = ""


    # CLEAN NAME
    clean = re.sub(r'[^A-Za-z0-9]', '', name)

    if not clean:
        clean = "Profile"


    # FILE NAME
    file_name = f"PTN_IN_RGSID_{clean}{mmdd}.docx"

    doc.save(file_name)


    # DOWNLOAD BUTTON
    with open(file_name, "rb") as file:
        st.download_button(
            label="Download TCS Profile",
            data=file,
            file_name=file_name
        )
