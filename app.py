import streamlit as st
from docxtpl import DocxTemplate
import re
from datetime import datetime, timedelta
import holidays
from dateutil import parser
import pytz


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="TCS Profile Generator",
    page_icon="📄",
    layout="wide"
)

st.title("📄 TCS Profile Generator")


# ============================================================
# USER INPUT
# ============================================================

email_text = st.text_area(
    "Paste Candidate Email / Naukri / Resdex / Resume Data",
    height=350
)

tracker_format = st.text_input(
    "Paste Tracker Columns (TAB separated)",
    placeholder=(
        "Dates\tBeeline ID\tCandidate Name\tContact Number\t"
        "Email ID\tSkill\tTotal Exp"
    )
)

manual_phone = st.text_input(
    "Candidate Contact Number (Optional Override)",
    placeholder="Example: 9611481059"
)


# ============================================================
# BASIC CLEANING
# ============================================================

def clean(value):
    """
    Collapse whitespace into a single space.
    Use for normal single-value fields.
    """

    if not value:
        return ""

    value = str(value)

    value = value.replace("**", "")

    return re.sub(r"\s+", " ", value).strip()


def soft_clean(value):
    """
    Clean spaces/tabs but preserve newlines.
    """

    if not value:
        return ""

    value = str(value)

    value = value.replace("**", "")

    value = value.strip()

    value = re.sub(
        r"[ \t]+",
        " ",
        value
    )

    return value


def normalize_input(text):
    """
    Normalize copied Naukri / Resdex / email content.
    """

    if not text:
        return ""

    text = str(text)

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Convert escaped @ to normal @
    text = text.replace(r"\@", "@")

    # Remove zero-width characters
    text = text.replace("\u200b", "")

    # Convert non-breaking space
    text = text.replace("\xa0", " ")

    return text


# ============================================================
# GENERAL REGEX HELPER
# ============================================================

def get_best_match(
    pattern,
    text,
    flags=re.IGNORECASE | re.DOTALL
):
    """
    Return first useful regex match.
    """

    if not text:
        return ""

    try:
        matches = re.findall(
            pattern,
            text,
            flags
        )
    except re.error:
        return ""

    for match in matches:

        if isinstance(match, tuple):

            value = ""

            for item in match:

                if item:
                    value = item
                    break

        else:

            value = match

        value = clean(value)

        if value and value.lower() not in {
            "na",
            "n/a",
            "-",
            "none",
            "not available"
        }:
            return value

    return ""


# ============================================================
# PHONE VALIDATION
# ============================================================

def valid_phone(phone):
    """
    Validate Indian mobile number.
    """

    if not phone:
        return ""

    phone = re.sub(
        r"\D",
        "",
        str(phone)
    )

    # 10 digit
    if len(phone) == 10:

        if phone[0] in "6789":
            return phone

    # 91XXXXXXXXXX
    if len(phone) == 12:

        if phone.startswith("91"):

            phone = phone[-10:]

            if phone[0] in "6789":
                return phone

    return ""


# ============================================================
# EMAIL VALIDATION
# ============================================================

def valid_email(email):

    if not email:
        return ""

    email = clean(email)

    pattern = (
        r"^[A-Za-z0-9._%+\-]+@"
        r"[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"
    )

    if re.fullmatch(
        pattern,
        email
    ):
        return email

    return ""


# ============================================================
# PHONE EXTRACTION
# ============================================================

def extract_explicit_phone(text):
    """
    Extract phone numbers associated with phone/contact labels.
    """

    if not text:
        return ""

    patterns = [

        # Contact Number: 9611481059
        r"(?:Contact\s*Number|Contact\s*No\.?|"
        r"Mobile\s*Number|Mobile\s*No\.?|"
        r"Phone\s*Number|Phone\s*No\.?)"
        r"\s*[:\-]?\s*"
        r"(?:\+91[\s\-]?)?"
        r"([6-9]\d{9})",

        # Contact: 9611481059
        r"(?:Contact|Mobile|Phone)"
        r"\s*[:\-]\s*"
        r"(?:\+91[\s\-]?)?"
        r"([6-9]\d{9})",

        # +91 9611481059
        r"(?<!\d)\+91[\s\-]?([6-9]\d{9})(?!\d)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            phone = valid_phone(
                match.group(1)
            )

            if phone:
                return phone

    return ""


def extract_naukri_phone(text):
    """
    Handles Naukri format:

    9611481059 (M)
    """

    if not text:
        return ""

    match = re.search(
        r"(?<!\d)"
        r"([6-9]\d{9})"
        r"\s*\(M\)",
        text,
        re.IGNORECASE
    )

    if match:

        return valid_phone(
            match.group(1)
        )

    return ""


def first_phone(text):
    """
    Conservative fallback phone extraction.
    """

    if not text:
        return ""

    # Remove URLs
    text_without_urls = re.sub(
        r"https?://\S+",
        " ",
        text,
        flags=re.IGNORECASE
    )

    # Remove emails
    text_without_urls = re.sub(
        r"\S+@\S+",
        " ",
        text_without_urls
    )

    candidates = re.findall(
        r"(?<![\dA-Za-z])"
        r"([6-9]\d{9})"
        r"(?![\dA-Za-z])",
        text_without_urls
    )

    for candidate in candidates:

        phone = valid_phone(candidate)

        if phone:
            return phone

    return ""


# ============================================================
# EMAIL EXTRACTION
# ============================================================

def first_email(text):

    if not text:
        return ""

    text = text.replace(
        r"\@",
        "@"
    )

    matches = re.findall(
        r"[A-Za-z0-9._%+\-]+"
        r"@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
        text
    )

    for email in matches:

        email = valid_email(email)

        if email:
            return email

    return ""


# ============================================================
# GENERIC NAME EXTRACTION
# ============================================================

def name_from_lines(text):

    if not text:
        return ""

    ignore_exact = {
        "naukri",
        "resdex",
        "profile",
        "candidate",
        "contact",
        "email",
        "phone",
        "mobile",
        "location",
        "experience",
        "skills",
        "key skills",
        "education",
        "employment",
        "attached cv",
        "verified",
        "active",
        "modified",
        "save",
        "forward",
        "schedule",
        "notice",
        "summary",
        "may also know",
        "work experience",
        "current location",
        "preferred location",
        "view phone number",
        "call candidate",
        "whatsapp",
        "send invite",
        "set reminder",
        "reports",
        "search",
        "jobs responses",
    }

    lines = []

    for raw_line in text.splitlines():

        line = clean(raw_line)

        if not line:
            continue

        line = re.sub(
            r"^[#*]+\s*",
            "",
            line
        )

        line = clean(line)

        if line:
            lines.append(line)

    for line in lines[:50]:

        low = line.lower()

        if low in ignore_exact:
            continue

        if any(
            low.startswith(prefix)
            for prefix in [
                "current",
                "profile",
                "candidate",
                "attached",
                "key skills",
                "work summary",
                "industry",
                "department",
                "role",
                "education",
                "save",
                "naukri",
                "resdex"
            ]
        ):
            continue

        if "@" in line:
            continue

        if re.search(
            r"https?://",
            line,
            re.IGNORECASE
        ):
            continue

        if re.search(
            r"\d{4,}",
            line
        ):
            continue

        if re.fullmatch(
            r"[A-Za-z][A-Za-z .'\-]{0,70}",
            line
        ):

            words = line.split()

            if 1 <= len(words) <= 5:

                return line.title()

    return ""


# ============================================================
# NORMAL / TCS EMAIL EXTRACTION
# ============================================================

def smart_extract(text):

    name = clean(
        get_best_match(
            r"Full Name\s*\(As per Aadhar\)"
            r"\s*:\s*(.*?)"
            r"\s*(?=Contact Number|Email ID|$)",
            text
        )
    )

    if not name:

        name = clean(
            get_best_match(
                r"(?:Candidate Name|Full Name|Name)"
                r"\s*:\s*"
                r"([A-Za-z][A-Za-z .'\-]{1,80})",
                text
            )
        )

    phone = extract_explicit_phone(text)

    email = first_email(text)

    dob_raw = clean(
        get_best_match(
            r"Date of Birth\s*:\s*"
            r"([0-9]{1,2}"
            r"(?:[\/\- ]+[A-Za-z0-9]+){1,3})",
            text
        )
    )

    location = clean(
        get_best_match(
            r"\bCurrent\s*Location\b"
            r"\s*[:\-]?\s*([^\n\r]+)",
            text
        )
    )

    pref_location = clean(
        get_best_match(
            r"Preferred Location\s*:\s*(.*?)"
            r"\s*(?=Compliance|Notice Period|Offers|$)",
            text
        )
    )

    skills = soft_clean(
        get_best_match(
            r"Skill Set\s*:\s*(.*?)"
            r"\s*(?=Total Experience|"
            r"Relevant Experience|Compliance|"
            r"Notice Period|$)",
            text
        )
    )

    exp = clean(
        get_best_match(
            r"Relevant Experience\s*:\s*"
            r"([0-9\+\.\s]*"
            r"(?:Years|Year|yrs|yr)"
            r"(?:\s*[0-9]{1,2}\s*"
            r"(?:Months?|Mos?|M))?)",
            text
        )
    )

    if not exp:

        exp = clean(
            get_best_match(
                r"Total Experience\s*:\s*([^\n\r]+)",
                text
            )
        )

    notice = clean(
        get_best_match(
            r"Notice Period\s*"
            r"(?:/ Last Working Date)?"
            r"\s*:\s*([^\n\r]+)",
            text
        )
    )

    offer = clean(
        get_best_match(
            r"Offers?\s*"
            r"(?:in Pipeline\s*/\s*In Hand|"
            r"in Pipeline|In Hand)?"
            r"\s*:\s*([^\n\r]+)",
            text
        )
    )

    reason = clean(
        get_best_match(
            r"Exact Reason for Change"
            r"\s*:\s*([^\n\r]+)",
            text
        )
    )

    return {
        "Full Name": name,
        "Contact Number": phone,
        "Email ID": email,
        "Current Location": location,
        "Preferred Location": pref_location,
        "Skills": skills,
        "Experience": exp,
        "Date of Birth": dob_raw,
        "Notice Period": notice,
        "Offers": offer,
        "Reason": reason,
    }


# ============================================================
# NAUKRI NAME EXTRACTION
# ============================================================

def extract_naukri_name(text):

    if not text:
        return ""

    text = normalize_input(text)

    ignored = {
        "jobs responses",
        "resdex",
        "ai rex",
        "premiumx",
        "reports",
        "search",
        "profile",
        "save",
        "candidate",
        "naukri"
    }

    # --------------------------------------------------------
    # 1. Naukri Markdown heading
    #
    # # Nuthan
    # ## Nuthan
    # **# Nuthan**
    # --------------------------------------------------------

    heading_pattern = (
        r"(?m)^\s*\*{0,2}\s*#+\s*"
        r"([^\n\r#]+?)"
        r"\s*\*{0,2}\s*$"
    )

    matches = re.findall(
        heading_pattern,
        text
    )

    for value in matches:

        value = clean(value)

        value = value.replace(
            "*",
            ""
        ).strip()

        if not value:
            continue

        if value.lower() in ignored:
            continue

        if re.fullmatch(
            r"[A-Za-z][A-Za-z .'\-]{0,70}",
            value
        ):
            return value.title()

    # --------------------------------------------------------
    # 2. Name immediately before experience
    #
    # # Nuthan
    # 4y 7m
    # --------------------------------------------------------

    match = re.search(
        r"(?m)^\s*"
        r"(?:\*{0,2}\s*)?"
        r"#+\s*"
        r"([A-Za-z][A-Za-z .'\-]{0,70})"
        r"\s*"
        r"(?:\*{0,2})"
        r"\s*\n\s*"
        r"\d{1,2}\s*y"
        r"(?:\s*\d{1,2}\s*m)?",
        text,
        re.IGNORECASE
    )

    if match:

        value = clean(
            match.group(1)
        )

        if value.lower() not in ignored:

            if re.fullmatch(
                r"[A-Za-z][A-Za-z .'\-]{0,70}",
                value
            ):
                return value.title()

    # --------------------------------------------------------
    # 3. Explicit name field
    # --------------------------------------------------------

    match = re.search(
        r"(?:Candidate\s*Name|"
        r"Full\s*Name|Name)"
        r"\s*[:\-]\s*"
        r"([A-Za-z][A-Za-z .'\-]{1,80})",
        text,
        re.IGNORECASE
    )

    if match:

        value = clean(
            match.group(1)
        )

        if value:
            return value.title()

    # --------------------------------------------------------
    # 4. Generic fallback around experience
    # --------------------------------------------------------

    lines = text.splitlines()

    for i, raw_line in enumerate(lines[:20]):

        line = clean(raw_line)

        if not line:
            continue

        line = re.sub(
            r"^[#*]+\s*",
            "",
            line
        ).strip()

        if i + 1 < len(lines):

            next_line = clean(
                lines[i + 1]
            )

            if re.fullmatch(
                r"\d{1,2}\s*y"
                r"(?:\s*\d{1,2}\s*m)?",
                next_line,
                re.IGNORECASE
            ):

                if re.fullmatch(
                    r"[A-Za-z][A-Za-z .'\-]{0,70}",
                    line
                ):

                    if line.lower() not in ignored:
                        return line.title()

    return ""


# ============================================================
# NAUKRI LOCATION
# ============================================================

def extract_naukri_location(text):

    # --------------------------------------------------------
    # Typical Naukri header
    #
    # ₹ 10 Lacs (expects: ₹ 13 Lacs)
    # Bengaluru
    # CurrentSenior Cloud Engineer...
    # --------------------------------------------------------

    match = re.search(
        r"₹\s*[\d,.]+\s*Lacs?"
        r"(?:\s*\(.*?\))?"
        r"\s*\n\s*"
        r"([A-Za-z][A-Za-z .&/\-]{2,50})"
        r"\s*\n\s*Current",
        text,
        re.IGNORECASE
    )

    if match:

        location = clean(
            match.group(1)
        )

        if location.lower() not in {
            "previous",
            "current",
            "save",
            "profile"
        }:
            return location

    # --------------------------------------------------------
    # Explicit Current Location
    # --------------------------------------------------------

    match = re.search(
        r"Current\s*Location"
        r"\s*[:\-]?\s*([^\n\r]+)",
        text,
        re.IGNORECASE
    )

    if match:

        location = clean(
            match.group(1)
        )

        if location.lower() not in {
            "na",
            "n/a",
            "-",
            "none"
        }:
            return location

    return ""


# ============================================================
# PREFERRED LOCATIONS
# ============================================================

def extract_preferred_locations(text):

    # --------------------------------------------------------
    # Naukri:
    #
    # Pref. locationsBengaluru, Remote, Chennai, Pune, Hyderabad
    #
    # followed by:
    # 9611481059 (M)
    # --------------------------------------------------------

    match = re.search(
        r"Pref\.?\s*locations?\s*[:\-]?\s*"
        r"(.+?)"
        r"(?="
        r"\n\s*(?:\*{0,2})?"
        r"[6-9]\d{9}\s*\(M\)"
        r"|"
        r"\n\s*(?:\*{0,2})?Call candidate"
        r"|"
        r"\n\s*(?:\*{0,2})?WhatsApp"
        r"|"
        r"\n\s*(?:\*{0,2})?View phone number"
        r"|$)",
        text,
        re.IGNORECASE | re.DOTALL
    )

    if match:

        value = match.group(1)

        # Remove phone if captured
        value = re.sub(
            r",?\s*[6-9]\d{9}\s*\(M\)",
            "",
            value
        )

        value = value.replace(
            "**",
            ""
        )

        # Newlines to comma
        value = re.sub(
            r"\s*\n\s*",
            ", ",
            value
        )

        # Duplicate commas
        value = re.sub(
            r",\s*,+",
            ", ",
            value
        )

        return clean(value)

    # --------------------------------------------------------
    # TCS / normal format
    # --------------------------------------------------------

    value = get_best_match(
        r"Preferred Location\s*:\s*(.*?)"
        r"(?=Compliance|Notice Period|Offers|$)",
        text
    )

    return clean(value)


# ============================================================
# NAUKRI SKILLS
# ============================================================

def extract_naukri_skills(text):

    if not text:
        return ""

    match = re.search(
        r"(?:##\s*)?Key skills\s*"
        r"(.*?)"
        r"(?="
        r"\n\s*(?:\[.*?View IT skills.*?\])?"
        r"\s*(?:May also know|"
        r"##\s*May also know|"
        r"Work summary|"
        r"##\s*Work summary|"
        r"Profile Summary|"
        r"Employment|"
        r"Education|"
        r"Activity|"
        r"$"
        r")",
        text,
        re.IGNORECASE | re.DOTALL
    )

    if not match:
        return ""

    skills_block = match.group(1)

    skills_block = skills_block.replace(
        "**",
        ""
    )

    skills_block = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        skills_block
    )

    return skills_block.strip()


# ============================================================
# NAUKRI EXPERIENCE
# ============================================================

def extract_naukri_experience(text):

    if not text:
        return ""

    # --------------------------------------------------------
    # 4y 7m
    # --------------------------------------------------------

    match = re.search(
        r"\b"
        r"([0-9]{1,2}\s*y\s*"
        r"[0-9]{1,2}\s*m)"
        r"\b",
        text,
        re.IGNORECASE
    )

    if match:
        return clean(
            match.group(1)
        )

    # --------------------------------------------------------
    # 4y
    # --------------------------------------------------------

    match = re.search(
        r"\b"
        r"([0-9]{1,2}(?:\.[0-9]{1,2})?\+?\s*y)"
        r"\b",
        text,
        re.IGNORECASE
    )

    if match:
        return clean(
            match.group(1)
        )

    # --------------------------------------------------------
    # 4 years / 4.7 years
    # --------------------------------------------------------

    match = re.search(
        r"(?<!\.)\b"
        r"([0-9]{1,2}(?:\.[0-9]{1,2})?"
        r"\+?\s*(?:Years?|Yrs?|Yr))"
        r"\b",
        text,
        re.IGNORECASE
    )

    if match:
        return clean(
            match.group(1)
        )

    return ""


# ============================================================
# DOB EXTRACTION
# ============================================================

def extract_dob(text):

    if not text:
        return ""

    # --------------------------------------------------------
    # 1. Explicit:
    # Date of Birth: 16 Sep 1994
    # --------------------------------------------------------

    patterns = [

        r"(?:Date of Birth|DOB|D\.O\.B)"
        r"\s*[:\-]?\s*"
        r"([0-9]{1,2}\s+"
        r"[A-Za-z]{3,9}\s+"
        r"[0-9]{4})",

        r"(?:Date of Birth|DOB|D\.O\.B)"
        r"\s*[:\-]?\s*"
        r"([0-9]{1,2}"
        r"[\/\-]"
        r"[0-9]{1,2}"
        r"[\/\-]"
        r"[0-9]{2,4})",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            return clean(
                match.group(1)
            )

    # --------------------------------------------------------
    # 2. Naukri personal details
    #
    # Date of Birth | Gender | Marital status | Category
    # 16 Sep 1994   | Male   | ...
    # --------------------------------------------------------

    table_match = re.search(
        r"Date of Birth.*?"
        r"\n\s*"
        r"(?:\*\*)?"
        r"([0-9]{1,2}\s+"
        r"[A-Za-z]{3,9}\s+"
        r"[0-9]{4})"
        r"(?:\*\*)?",
        text,
        re.IGNORECASE | re.DOTALL
    )

    if table_match:

        return clean(
            table_match.group(1)
        )

    # --------------------------------------------------------
    # 3. Line fallback
    # --------------------------------------------------------

    lines = text.splitlines()

    for i, line in enumerate(lines):

        if "Date of Birth" in line:

            for next_line in lines[i + 1:i + 5]:

                match = re.search(
                    r"\b"
                    r"([0-9]{1,2}\s+"
                    r"[A-Za-z]{3,9}\s+"
                    r"[0-9]{4})"
                    r"\b",
                    next_line
                )

                if match:

                    return match.group(1)

    return ""


# ============================================================
# OFFER
# ============================================================

def extract_offer_status(text):

    return get_best_match(
        r"Offers?\s*"
        r"(?:in Pipeline\s*/\s*In Hand|"
        r"in Pipeline|In Hand)?"
        r"\s*:\s*([^\n\r]+)",
        text
    )


# ============================================================
# REASON
# ============================================================

def extract_reason(text):

    return get_best_match(
        r"Exact Reason for Change"
        r"\s*:\s*([^\n\r]+)",
        text
    )


# ============================================================
# NOTICE PERIOD
# ============================================================

def extract_notice_period(text):
    """
    Business rule:
    Every generated TCS profile should display
    Immediate Joiner.
    """

    return "Immediate Joiner"


# ============================================================
# NAUKRI COMPLETE EXTRACTION
# ============================================================

def naukri_extract(text):

    name = extract_naukri_name(text)

    phone = (
        extract_explicit_phone(text)
        or extract_naukri_phone(text)
    )

    email = first_email(text)

    location = extract_naukri_location(text)

    preferred_location = extract_preferred_locations(text)

    skills = extract_naukri_skills(text)

    experience = extract_naukri_experience(text)

    dob = extract_dob(text)

    notice = extract_notice_period(text)

    offer = extract_offer_status(text)

    reason = extract_reason(text)

    return {
        "Full Name": name,
        "Contact Number": phone,
        "Email ID": email,
        "Current Location": location,
        "Preferred Location": preferred_location,
        "Skills": skills,
        "Experience": experience,
        "Date of Birth": dob,
        "Notice Period": notice,
        "Offers": offer,
        "Reason": reason,
    }


# ============================================================
# AUTO EXTRACTION
# ============================================================

def auto_extract(text):

    text = normalize_input(text)

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
        "Notice Period",
        "Offers",
        "Reason",
    ]

    # Naukri fields should have priority
    naukri_priority = {
        "Full Name",
        "Current Location",
        "Preferred Location",
        "Skills",
        "Experience",
        "Date of Birth",
        "Notice Period",
    }

    for key in fields:

        normal_value = normal_data.get(
            key,
            ""
        )

        naukri_value = naukri_data.get(
            key,
            ""
        )

        # ----------------------------------------------------
        # Phone
        # ----------------------------------------------------

        if key == "Contact Number":

            final[key] = (
                valid_phone(normal_value)
                or valid_phone(naukri_value)
                or ""
            )

        # ----------------------------------------------------
        # Email
        # ----------------------------------------------------

        elif key == "Email ID":

            final[key] = (
                valid_email(normal_value)
                or valid_email(naukri_value)
                or ""
            )

        # ----------------------------------------------------
        # Naukri priority fields
        # ----------------------------------------------------

        elif key in naukri_priority:

            final[key] = (
                naukri_value
                or normal_value
                or ""
            )

        # ----------------------------------------------------
        # Other fields
        # ----------------------------------------------------

        else:

            final[key] = (
                normal_value
                or naukri_value
                or ""
            )

    return final


# ============================================================
# EXPERIENCE FORMAT
# ============================================================

def format_experience(exp):

    if not exp:
        return ""

    exp = clean(exp)

    # --------------------------------------------------------
    # 4y 7m -> 4.7 years
    #
    # This follows your required display convention.
    # --------------------------------------------------------

    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)"
        r"\s*y\s*"
        r"(\d+)"
        r"\s*m",
        exp,
        re.IGNORECASE
    )

    if match:

        years = match.group(1)

        months = match.group(2)

        return f"{years}.{months} years"

    # --------------------------------------------------------
    # 4y -> 4 years
    # --------------------------------------------------------

    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)"
        r"\s*y",
        exp,
        re.IGNORECASE
    )

    if match:

        return f"{match.group(1)} years"

    # --------------------------------------------------------
    # 4 years / 4.7 years
    # --------------------------------------------------------

    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)"
        r"\s*(?:years?|yrs?|yr)",
        exp,
        re.IGNORECASE
    )

    if match:

        return f"{match.group(1)} years"

    return exp


# ============================================================
# DOB -> MMDD
# ============================================================

def get_mmdd(dob):

    if not dob:
        return ""

    try:

        parsed_date = parser.parse(
            dob,
            dayfirst=True
        )

        return parsed_date.strftime(
            "%m%d"
        )

    except Exception:

        return ""


# ============================================================
# SKILL CLEANING
# ============================================================

NOISE_SKILLS = {
    "view it skills",
    "view it skill",
    "view more",
    "show more",
    "show all",
    "view all",
    "more",
    "save",
}


def clean_skill(skill):

    if not skill:
        return ""

    skill = skill.strip()

    skill = skill.replace(
        "**",
        ""
    )

    # Markdown links
    skill = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        skill
    )

    # Bullets
    skill = re.sub(
        r"^[•\-\*]+\s*",
        "",
        skill
    )

    skill = re.sub(
        r"\s+",
        " ",
        skill
    ).strip()

    return skill


def extract_top_skills(skills_raw):

    if not skills_raw:
        return []

    skills_raw = skills_raw.replace(
        "**",
        ""
    )

    lines = skills_raw.splitlines()

    skill_list = []

    for line in lines:

        skill = clean_skill(line)

        if not skill:
            continue

        if skill.lower() in NOISE_SKILLS:
            continue

        if (
            "http://" in skill.lower()
            or "https://" in skill.lower()
        ):
            continue

        # Handle pipe separated skills
        parts = re.split(
            r"\|",
            skill
        )

        for part in parts:

            part = clean_skill(part)

            if not part:
                continue

            if part.lower() in NOISE_SKILLS:
                continue

            # Avoid duplicate skills
            if part.lower() not in [
                x.lower()
                for x in skill_list
            ]:

                skill_list.append(
                    part
                )

    # --------------------------------------------------------
    # If copied content flattened all skills into one line
    # --------------------------------------------------------

    if len(skill_list) <= 1:

        skill_list = []

        parts = re.split(
            r",|;|\n|\|",
            skills_raw
        )

        for part in parts:

            skill = clean_skill(part)

            if not skill:
                continue

            if skill.lower() in NOISE_SKILLS:
                continue

            if skill.lower() not in [
                x.lower()
                for x in skill_list
            ]:

                skill_list.append(
                    skill
                )

    return skill_list


# ============================================================
# INTERVIEW DATE LOGIC
# ============================================================

def get_interview_dates():

    ist = pytz.timezone(
        "Asia/Kolkata"
    )

    now = datetime.now(ist)

    india_holidays = holidays.India(
        years=[
            now.year,
            now.year + 1
        ]
    )

    current = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    cutoff = now.replace(
        hour=14,
        minute=0,
        second=0,
        microsecond=0
    )

    # After / at 2 PM -> start next day
    if now >= cutoff:

        current += timedelta(
            days=1
        )

    dates = []

    while len(dates) < 3:

        if (
            current.weekday() < 5
            and current.date() not in india_holidays
        ):

            dates.append(
                current.strftime(
                    "%d-%b-%Y"
                )
            )

        current += timedelta(
            days=1
        )

    return dates, now


# ============================================================
# TRACKER
# ============================================================

def generate_tracker_row(
    tracker_format,
    name,
    phone,
    email,
    skill_list,
    exp,
    location,
    pref_location,
    dob,
    now
):

    if not tracker_format:
        return ""

    tracker_cols = tracker_format.split(
        "\t"
    )

    def get_value(column):

        col = clean(
            column
        ).lower()

        # ----------------------------------------------------
        # Candidate name
        # ----------------------------------------------------

        if col in {
            "candidate name",
            "resource name",
            "name",
            "resource name (as per pan card)"
        }:

            return name

        # ----------------------------------------------------
        # Phone
        # ----------------------------------------------------

        if (
            "contact number" in col
            or col in {
                "contact",
                "phone",
                "mobile"
            }
        ):

            return phone

        # ----------------------------------------------------
        # Email
        # ----------------------------------------------------

        if (
            "email id" in col
            or col == "email"
        ):

            return email

        # ----------------------------------------------------
        # Skill
        # ----------------------------------------------------

        if (
            col == "skill"
            or col == "skills"
            or "primary skill" in col
            or "skill name" in col
        ):

            return ", ".join(
                skill_list
            )

        # ----------------------------------------------------
        # Experience
        # ----------------------------------------------------

        if (
            "total exp" in col
            or "total experience" in col
            or "relevant exp" in col
            or "relevant experience" in col
        ):

            return exp

        # ----------------------------------------------------
        # Current location
        # ----------------------------------------------------

        if "current location" in col:

            return location

        # ----------------------------------------------------
        # Preferred / relocation
        # ----------------------------------------------------

        if (
            "preferred location" in col
            or col.startswith("pref")
            or "relocation" in col
        ):

            return pref_location

        # ----------------------------------------------------
        # DOB
        # ----------------------------------------------------

        if (
            "dob" in col
            or "date of birth" in col
            or "birth" in col
        ):

            return dob

        # ----------------------------------------------------
        # Date
        # ----------------------------------------------------

        if "date" in col:

            return now.strftime(
                "%d-%m-%Y"
            )

        return ""

    row = [
        get_value(column)
        for column in tracker_cols
    ]

    return "\t".join(row)


# ============================================================
# GENERATE BUTTON
# ============================================================

if st.button(
    "Generate TCS Profile",
    type="primary"
):

    # ========================================================
    # INPUT VALIDATION
    # ========================================================

    if not email_text.strip():

        st.warning(
            "Please paste candidate Email / "
            "Naukri / Resdex data."
        )

        st.stop()

    # ========================================================
    # NORMALIZE + EXTRACT
    # ========================================================

    source_text = normalize_input(
        email_text
    )

    data = auto_extract(
        source_text
    )

    # ========================================================
    # NAME
    # ========================================================

    name = clean(
        data.get(
            "Full Name",
            ""
        )
    )

    # ========================================================
    # PHONE
    # ========================================================

    # Manual override has highest priority
    phone = valid_phone(
        manual_phone
    )

    if not phone:

        phone = valid_phone(
            data.get(
                "Contact Number",
                ""
            )
        )

    if not phone:

        phone = first_phone(
            source_text
        )

    # ========================================================
    # EMAIL
    # ========================================================

    email = valid_email(
        data.get(
            "Email ID",
            ""
        )
    )

    # ========================================================
    # LOCATION
    # ========================================================

    location = clean(
        data.get(
            "Current Location",
            ""
        )
    )

    pref_location = clean(
        data.get(
            "Preferred Location",
            ""
        )
    )

    # ========================================================
    # EXPERIENCE
    # ========================================================

    exp_raw = clean(
        data.get(
            "Experience",
            ""
        )
    )

    exp = format_experience(
        exp_raw
    )

    # ========================================================
    # DOB
    # ========================================================

    dob = clean(
        data.get(
            "Date of Birth",
            ""
        )
    )

    mmdd = get_mmdd(
        dob
    )

    # ========================================================
    # SKILLS
    # ========================================================

    skills_raw = data.get(
        "Skills",
        ""
    )

    actual_skill_list = extract_top_skills(
        skills_raw
    )

    # Keep first 3 only after validation
    if len(actual_skill_list) >= 3:

        skill_list = actual_skill_list[:3]

    else:

        skill_list = actual_skill_list[:]

        while len(skill_list) < 3:

            skill_list.append("")

    # ========================================================
    # NOTICE / OFFER / REASON
    # ========================================================

    notice_period = clean(
        data.get(
            "Notice Period",
            ""
        )
    )

    # Business rule
    if not notice_period:

        notice_period = "Immediate Joiner"

    offer = clean(
        data.get(
            "Offers",
            ""
        )
    )

    reason = clean(
        data.get(
            "Reason",
            ""
        )
    )

    # --------------------------------------------------------
    # Current defaults
    #
    # Keep these if they are your TCS business rules.
    # --------------------------------------------------------

    if not offer:

        offer = "No"

    if not reason:

        reason = "Career Growth"

    # ========================================================
    # VALIDATION
    # IMPORTANT:
    # This happens BEFORE DOCX generation.
    # ========================================================

    missing_fields = []

    if not name:

        missing_fields.append(
            "Candidate Name"
        )

    if not phone:

        missing_fields.append(
            "Contact Number"
        )

    if not email:

        missing_fields.append(
            "Email ID"
        )

    if not location:

        missing_fields.append(
            "Current Location"
        )

    if not exp:

        missing_fields.append(
            "Experience"
        )

    if not dob:

        missing_fields.append(
            "Date of Birth"
        )

    if not mmdd:

        missing_fields.append(
            "Valid DOB for filename"
        )

    if len(actual_skill_list) < 3:

        missing_fields.append(
            "At least 3 Skills"
        )

    # --------------------------------------------------------
    # Stop if anything mandatory is missing
    # --------------------------------------------------------

    if missing_fields:

        st.error(
            "❌ Profile cannot be generated.\n\n"
            "Missing / unverified fields: "
            + ", ".join(missing_fields)
        )

        if not phone:

            st.info(
                "If Naukri shows 'View phone number', "
                "enter the actual candidate number in "
                "the Contact Number Override box."
            )

        st.stop()

    # ========================================================
    # INTERVIEW DATES
    # ========================================================

    dates, now = get_interview_dates()

    time_slot = "10:00AM-06:00PM"

    # ========================================================
    # DISPLAY EXTRACTED DATA
    # ========================================================

    st.subheader(
        "🔎 Extracted Candidate Details"
    )

    col1, col2 = st.columns(2)

    with col1:

        st.write(
            f"**Name:** {name}"
        )

        st.write(
            f"**Contact:** {phone}"
        )

        st.write(
            f"**Email:** {email}"
        )

        st.write(
            f"**Current Location:** {location}"
        )

        st.write(
            f"**Preferred Location:** "
            f"{pref_location or 'Not Found'}"
        )

    with col2:

        st.write(
            f"**Experience:** {exp}"
        )

        st.write(
            f"**DOB:** {dob}"
        )

        st.write(
            f"**Skill 1:** {skill_list[0]}"
        )

        st.write(
            f"**Skill 2:** {skill_list[1]}"
        )

        st.write(
            f"**Skill 3:** {skill_list[2]}"
        )

        st.write(
            f"**Notice Period:** {notice_period}"
        )

        st.write(
            f"**Offers:** {offer}"
        )

        st.write(
            f"**Reason:** {reason}"
        )

    # ========================================================
    # TEMPLATE FILE
    # ========================================================

    try:

        doc = DocxTemplate(
            "tcs_template.docx"
        )

    except Exception as e:

        st.error(
            "❌ Could not open "
            "tcs_template.docx"
        )

        st.exception(e)

        st.stop()

    # ========================================================
    # TEMPLATE CONTEXT
    # ========================================================

    context = {

        "NAME": name,

        "CONTACT_NUMBER": phone,

        "EMAIL_ID": email,

        "CURRENT_LOCATION": location,

        "PREFERRED_LOCATION": pref_location,

        "SKILL1": skill_list[0],

        "SKILL2": skill_list[1],

        "SKILL3": skill_list[2],

        # Experience
        "EXP1": exp,
        "EXP2": exp,
        "EXP3": exp,

        # Notice
        "NOTICE_PERIOD": notice_period,

        # Offer
        "OFFER": offer,

        # Relocation
        "RELOCATION": (
            pref_location
            if pref_location
            else location
        ),

        # Reason
        "REASON": reason,

        # DOB
        "DOB": dob,

        # Interview dates
        "NEXT_DATE1": dates[0],
        "NEXT_DATE2": dates[1],
        "NEXT_DATE3": dates[2],

        # Time
        "TIME": time_slot,
    }

    # ========================================================
    # RENDER DOCUMENT
    # ========================================================

    try:

        doc.render(
            context
        )

    except Exception as e:

        st.error(
            "❌ Error while rendering "
            "the Word template."
        )

        st.exception(e)

        st.stop()

    # ========================================================
    # FILE NAME
    # ========================================================

    safe_name = re.sub(
        r"[^A-Za-z0-9]",
        "",
        name
    )

    if not safe_name:

        safe_name = "Candidate"

    file_name = (
        f"PTN_IN_RGSID_"
        f"{safe_name}"
        f"{mmdd}.docx"
    )

    # Example:
    # Nuthan + 0916
    #
    # PTN_IN_RGSID_Nuthan0916.docx

    # ========================================================
    # SAVE
    # ========================================================

    try:

        doc.save(
            file_name
        )

    except Exception as e:

        st.error(
            "❌ Could not save generated "
            "Word file."
        )

        st.exception(e)

        st.stop()

    # ========================================================
    # DOWNLOAD
    # ========================================================

    with open(
        file_name,
        "rb"
    ) as file:

        st.download_button(
            label="📥 Download TCS Profile",
            data=file,
            file_name=file_name,
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            )
        )

    # ========================================================
    # SUCCESS
    # ========================================================

    st.success(
        f"✅ Profile Generated Successfully: "
        f"{file_name}"
    )

    # ========================================================
    # TRACKER
    # ========================================================

    if tracker_format:

        tracker_line = generate_tracker_row(
            tracker_format=tracker_format,
            name=name,
            phone=phone,
            email=email,
            skill_list=skill_list,
            exp=exp,
            location=location,
            pref_location=pref_location,
            dob=dob,
            now=now
        )

        st.subheader(
            "📊 Tracker Output (Copy Paste)"
        )

        st.code(
            tracker_line,
            language=None
        )

    # ========================================================
    # FINAL PROFILE SUMMARY
    # ========================================================

    st.subheader(
        "📄 Generated Profile Summary"
    )

    st.write(
        f"**File Name:** `{file_name}`"
    )

    st.write(
        f"**Candidate:** {name}"
    )

    st.write(
        f"**Contact:** {phone}"
    )

    st.write(
        f"**Email:** {email}"
    )

    st.write(
        f"**Experience:** {exp}"
    )

    st.write(
        f"**DOB:** {dob}"
    )

    st.write(
        f"**Notice Period:** "
        f"{notice_period}"
    )

    st.write(
        f"**Interview Dates:** "
        f"{dates[0]}, "
        f"{dates[1]}, "
        f"{dates[2]}"
    )

    st.write(
        f"**Time Slot:** {time_slot}"
    )
