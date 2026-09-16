import streamlit as st
from docxtpl import DocxTemplate
import re
from datetime import datetime, timedelta
import holidays
from dateutil import parser
import pytz


# ============================================================
# UI
# ============================================================

st.set_page_config(
    page_title="TCS Profile Generator",
    page_icon="📄",
    layout="wide"
)

st.title("📄 TCS Profile Generator")

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

# Optional manual phone override.
# Useful when Naukri displays "View phone number" and the actual number
# is not included in the copied profile text.
manual_phone = st.text_input(
    "Candidate Contact Number (Optional Override)",
    placeholder="Example: 9611481059"
)


# ============================================================
# BASIC CLEANING
# ============================================================

def clean(value):
    """
    Collapse all whitespace into one space.
    Suitable for normal single-value fields.
    """
    if not value:
        return ""

    value = str(value)

    # Remove markdown bold
    value = value.replace("**", "")

    return re.sub(r"\s+", " ", value).strip()


def soft_clean(value):
    """
    Preserve newlines while cleaning spaces/tabs.
    Useful for Skills where each line may represent one skill.
    """
    if not value:
        return ""

    value = str(value)

    # Remove markdown bold
    value = value.replace("**", "")

    value = value.strip()

    # Normalize spaces/tabs only
    value = re.sub(r"[ \t]+", " ", value)

    return value


def normalize_input(text):
    """
    Normalize common copied Naukri / Resdex / email formatting.
    """
    if not text:
        return ""

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Markdown / escaped characters
    text = text.replace(r"\@", "@")

    # Remove zero-width characters
    text = text.replace("\u200b", "")
    text = text.replace("\xa0", " ")

    return text


# ============================================================
# GENERAL REGEX HELPER
# ============================================================

def get_best_match(pattern, text, flags=re.IGNORECASE | re.DOTALL):
    """
    Return first useful regex match.
    """
    try:
        matches = re.findall(pattern, text, flags)
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

        if value and value.lower() not in [
            "na",
            "n/a",
            "-",
            "none",
            "not available"
        ]:
            return value

    return ""


# ============================================================
# VALIDATORS
# ============================================================

def valid_phone(phone):
    """
    Validate Indian 10-digit mobile number.
    """
    if not phone:
        return ""

    phone = re.sub(r"\D", "", phone)

    if len(phone) == 10 and phone[0] in "6789":
        return phone

    if len(phone) == 12 and phone.startswith("91"):
        phone = phone[-10:]

        if phone[0] in "6789":
            return phone

    return ""


def valid_email(email):
    """
    Basic email validation.
    """
    if not email:
        return ""

    email = clean(email)

    pattern = r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"

    if re.fullmatch(pattern, email):
        return email

    return ""


# ============================================================
# PHONE EXTRACTION
# ============================================================

def extract_explicit_phone(text):
    """
    Extract phone only when it is explicitly associated with a phone/contact
    label.

    This prevents accidentally extracting numbers from:
    - Naukri URLs
    - uniqId
    - uresid
    - job IDs
    - other page metadata
    """

    patterns = [

        # Contact Number: 9611481059
        r"(?:Contact\s*Number|Contact\s*No\.?|Mobile\s*Number|Mobile\s*No\.?|Phone\s*Number|Phone\s*No\.?)\s*[:\-]?\s*(?:\+91[\s\-]?)?([6-9]\d{9})",

        # Contact: 9611481059
        r"(?:Contact|Mobile|Phone)\s*[:\-]\s*(?:\+91[\s\-]?)?([6-9]\d{9})",

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

            phone = valid_phone(match.group(1))

            if phone:
                return phone

    return ""


def first_phone(text):
    """
    Fallback phone extraction.

    IMPORTANT:
    Do not blindly take the first 10-digit number from Naukri text,
    because Naukri URLs may contain 10-digit numeric IDs.

    Only accept a standalone Indian mobile number if it is not obviously
    part of a URL/ID.
    """

    # Remove URLs first
    text_without_urls = re.sub(
        r"https?://\S+",
        " ",
        text,
        flags=re.IGNORECASE
    )

    # Remove email addresses
    text_without_urls = re.sub(
        r"\S+@\S+",
        " ",
        text_without_urls
    )

    candidates = re.findall(
        r"(?<![\dA-Za-z])([6-9]\d{9})(?![\dA-Za-z])",
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

    text = text.replace(r"\@", "@")

    matches = re.findall(
        r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
        text
    )

    for email in matches:

        email = valid_email(email)

        if email:
            return email

    return ""


# ============================================================
# NAME EXTRACTION
# ============================================================

def name_from_lines(text):

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
        "send nvite",
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

        # Remove markdown heading
        line = re.sub(r"^#+\s*", "", line)

        line = clean(line)

        if line:
            lines.append(line)

    # First pass:
    # Naukri profile usually places candidate name near the beginning.
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

        if re.search(r"https?://", line, re.IGNORECASE):
            continue

        if re.search(r"\d{4,}", line):
            continue

        # Name can be one word or multiple words.
        if re.fullmatch(
            r"[A-Za-z][A-Za-z .'\-]{1,70}",
            line
        ):

            words = line.split()

            if 1 <= len(words) <= 5:

                # Avoid obvious UI words
                if low not in ignore_exact:
                    return line.title()

    return ""


# ============================================================
# NORMAL / TCS EMAIL EXTRACTION
# ============================================================

def smart_extract(text):

    name = clean(get_best_match(
        r"Full Name\s*\(As per Aadhar\)\s*:\s*(.*?)\s*(?=Contact Number|Email ID|$)",
        text
    ))

    if not name:
        name = clean(get_best_match(
            r"(?:Candidate Name|Full Name|Name)\s*:\s*([A-Za-z][A-Za-z .'\-]{1,80})",
            text
        ))

    phone = extract_explicit_phone(text)

    email = first_email(text)

    dob_raw = clean(get_best_match(
        r"Date of Birth\s*:\s*([0-9]{1,2}(?:[\/\- ]+[A-Za-z0-9]+){1,3})",
        text
    ))

    location = clean(get_best_match(
        r"\bCurrent\s*Location\b\s*[:\-]?\s*([^\n\r]+)",
        text
    ))

    pref_location = clean(get_best_match(
        r"Preferred Location\s*:\s*(.*?)\s*(?=Compliance|Notice Period|Offers|$)",
        text
    ))

    skills = soft_clean(get_best_match(
        r"Skill Set\s*:\s*(.*?)\s*(?=Total Experience|Relevant Experience|Compliance|Notice Period|$)",
        text
    ))

    exp = clean(get_best_match(
        r"Relevant Experience\s*:\s*([0-9\+\.\s]*(?:Years|Year|yrs|yr)(?:\s*[0-9]{1,2}\s*(?:Months?|Mos?|M))?)",
        text
    ))

    if not exp:
        exp = clean(get_best_match(
            r"Total Experience\s*:\s*([^\n\r]+)",
            text
        ))

    notice = clean(get_best_match(
        r"Notice Period\s*(?:/ Last Working Date)?\s*:\s*([^\n\r]+)",
        text
    ))

    offer = clean(get_best_match(
        r"Offers?\s*(?:in Pipeline\s*/\s*In Hand|in Pipeline|In Hand)?\s*:\s*([^\n\r]+)",
        text
    ))

    reason = clean(get_best_match(
        r"Exact Reason for Change\s*:\s*([^\n\r]+)",
        text
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
        "Notice Period": notice,
        "Offers": offer,
        "Reason": reason,
    }


# ============================================================
# NAUKRI / RESDEX EXTRACTION
# ============================================================

def extract_naukri_name(text):

    # --------------------------------------------------------
    # 1. Naukri profile heading
    # Example:
    # # Nuthan
    # --------------------------------------------------------

    matches = re.findall(
        r"(?m)^#+\s*([A-Za-z][A-Za-z .'\-]{1,70})\s*$",
        text
    )

    for value in matches:

        value = clean(value)

        if value.lower() in {
            "jobs responses",
            "resdex",
            "ai rex",
            "premiumx",
            "reports",
            "search",
            "profile",
            "save"
        }:
            continue

        if re.fullmatch(
            r"[A-Za-z][A-Za-z .'\-]{1,70}",
            value
        ):
            return value.title()

    # --------------------------------------------------------
    # 2. Explicit name
    # --------------------------------------------------------

    name = get_best_match(
        r"(?:Candidate Name|Full Name|Name)\s*[:\-]\s*"
        r"([A-Za-z][A-Za-z .'\-]{1,80})",
        text
    )

    if name:
        return name.title()

    return ""

def extract_naukri_location(text):

    # --------------------------------------------------------
    # Naukri header format
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

        location = clean(match.group(1))

        # Safety checks
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
        r"Current\s*Location\s*[:\-]?\s*([^\n\r]+)",
        text,
        re.IGNORECASE
    )

    if match:

        location = clean(match.group(1))

        if location.lower() not in {
            "na",
            "n/a",
            "-",
            "none"
        }:
            return location

    return ""

def extract_preferred_locations(text):

    # --------------------------------------------------------
    # Naukri format:
    #
    # Pref. locationsBengaluru, Remote, Chennai, Pune, Hyderabad
    #
    # Stop before phone number / Call candidate / WhatsApp
    # --------------------------------------------------------

    match = re.search(
        r"Pref\.?\s*locations?\s*[:\-]?\s*"
        r"(.+?)"
        r"(?=\n\s*(?:\*{0,2})?(?:[6-9]\d{9})\s*\(M\)"
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

        # Remove phone if it somehow entered the match
        value = re.sub(
            r",?\s*[6-9]\d{9}\s*\(M\)",
            "",
            value
        )

        value = value.replace("**", "")

        # Newlines -> comma
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
    # TCS format
    # --------------------------------------------------------

    value = get_best_match(
        r"Preferred Location\s*:\s*(.*?)"
        r"(?=Compliance|Notice Period|Offers|$)",
        text
    )

    return clean(value)


def extract_naukri_skills(text):

    # --------------------------------------------------------
    # Locate Key Skills section without destroying newlines
    # --------------------------------------------------------

    match = re.search(
        r"(?:##\s*)?Key skills\s*"
        r"(.*?)"
        r"(?=\n\s*(?:\[.*?View IT skills.*?\])?"
        r"\s*(?:May also know|##\s*May also know|Work summary|"
        r"##\s*Work summary|Profile Summary|Employment|Education|Activity|$))",
        text,
        re.IGNORECASE | re.DOTALL
    )

    if not match:
        return ""

    skills_block = match.group(1)

    # Remove markdown bold
    skills_block = skills_block.replace("**", "")

    # Remove markdown links
    skills_block = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        skills_block
    )

    return skills_block.strip()


def extract_naukri_experience(text):

    # 4y 7m
    match = re.search(
        r"\b([0-9]{1,2}\s*y\s*[0-9]{1,2}\s*m)\b",
        text,
        re.IGNORECASE
    )

    if match:
        return clean(match.group(1))

    # 4y
    match = re.search(
        r"\b([0-9]{1,2}(?:\.[0-9]{1,2})?\+?\s*y)\b",
        text,
        re.IGNORECASE
    )

    if match:
        return clean(match.group(1))

    # 4 years / 4.7 years
    match = re.search(
        r"(?<!\.)\b([0-9]{1,2}(?:\.[0-9]{1,2})?\+?\s*(?:Years?|Yrs?|Yr))\b",
        text,
        re.IGNORECASE
    )

    if match:
        return clean(match.group(1))

    return ""


def extract_dob(text):

    # --------------------------------------------------------
    # 1. Explicit format
    # --------------------------------------------------------

    patterns = [

        # Date of Birth: 16 Sep 1994
        r"(?:Date of Birth|DOB|D\.O\.B)"
        r"\s*[:\-]?\s*"
        r"([0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4})",

        # Date of Birth: 16/09/1994
        r"(?:Date of Birth|DOB|D\.O\.B)"
        r"\s*[:\-]?\s*"
        r"([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            return clean(match.group(1))

    # --------------------------------------------------------
    # 2. Naukri Personal Details table
    #
    # Date of Birth | Gender | Marital status | Category
    # 16 Sep 1994   | Male   | ...
    # --------------------------------------------------------

    table_match = re.search(
        r"Date of Birth.*?"
        r"\n\s*"
        r"(?:\*\*)?"
        r"([0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4})"
        r"(?:\*\*)?",
        text,
        re.IGNORECASE | re.DOTALL
    )

    if table_match:
        return clean(
            table_match.group(1)
        )

    # --------------------------------------------------------
    # 3. Markdown table fallback
    # --------------------------------------------------------

    lines = text.splitlines()

    for i, line in enumerate(lines):

        if "Date of Birth" in line:

            # Look at next few lines
            for next_line in lines[i + 1:i + 4]:

                match = re.search(
                    r"\b([0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4})\b",
                    next_line
                )

                if match:
                    return match.group(1)

    return ""


def extract_offer_status(text):

    value = get_best_match(
        r"Offers?\s*(?:in Pipeline\s*/\s*In Hand|in Pipeline|In Hand)?\s*:\s*([^\n\r]+)",
        text
    )

    return value


def extract_reason(text):

    return get_best_match(
        r"Exact Reason for Change\s*:\s*([^\n\r]+)",
        text
    )

def extract_notice_period(text):
    """
    Always display Immediate Joiner in the TCS profile.
    """

    return "Immediate Joiner"
    
def naukri_extract(text):

    name = extract_naukri_name(text)

    phone = extract_explicit_phone(text)

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

    for key in fields:

        normal_value = normal_data.get(key, "")
        naukri_value = naukri_data.get(key, "")

        # Prefer normal/TCS extraction where valid
        if key == "Contact Number":

            final[key] = (
                valid_phone(normal_value)
                or valid_phone(naukri_value)
                or ""
            )

        elif key == "Email ID":

            final[key] = (
                valid_email(normal_value)
                or valid_email(naukri_value)
                or ""
            )

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

    # 4y 7m -> 4.7 years
    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*y\s*(\d+)\s*m",
        exp,
        re.IGNORECASE
    )

    if match:

        years = match.group(1)
        months = match.group(2)

        return f"{years}.{months} years"

    # 4y -> 4 years
    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*y",
        exp,
        re.IGNORECASE
    )

    if match:

        return f"{match.group(1)} years"

    # 4 years / 4.7 years
    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?|yr)",
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

        return parsed_date.strftime("%m%d")

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

    # Remove markdown
    skill = skill.replace("**", "")

    # Remove markdown links but preserve visible text
    skill = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        skill
    )

    # Remove bullets
    skill = re.sub(
        r"^[•\-\*]+\s*",
        "",
        skill
    )

    # Remove excess whitespace
    skill = re.sub(
        r"\s+",
        " ",
        skill
    ).strip()

    return skill


def extract_top_skills(skills_raw):

    if not skills_raw:
        return []

    skills_raw = skills_raw.replace("**", "")

    # --------------------------------------------------------
    # Split primarily by lines
    # --------------------------------------------------------

    lines = skills_raw.splitlines()

    skill_list = []

    for line in lines:

        skill = clean_skill(line)

        if not skill:
            continue

        # Remove bullet
        skill = re.sub(
            r"^[•\-\*]+\s*",
            "",
            skill
        )

        # Remove View IT skills
        if skill.lower() in NOISE_SKILLS:
            continue

        # Ignore markdown/UI
        if skill.lower() in {
            "view it skills",
            "view it skill",
            "view more",
            "show more",
            "save"
        }:
            continue

        if "http://" in skill.lower():
            continue

        if "https://" in skill.lower():
            continue

        # If a line contains | separators
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

            # Avoid duplicates
            if part.lower() not in [
                x.lower() for x in skill_list
            ]:
                skill_list.append(part)

    # --------------------------------------------------------
    # If lines were flattened, use known skill separators
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
                x.lower() for x in skill_list
            ]:
                skill_list.append(skill)

    return skill_list[:3]

# ============================================================
# INTERVIEW DATE LOGIC
# ============================================================

def get_interview_dates():

    ist = pytz.timezone("Asia/Kolkata")

    now = datetime.now(ist)

    india_holidays = holidays.India(
        years=[now.year, now.year + 1]
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

    # If after 2 PM, start from next day
    if now > cutoff:
        current += timedelta(days=1)

    dates = []

    while len(dates) < 3:

        if (
            current.weekday() < 5
            and current.date() not in india_holidays
        ):

            dates.append(
                current.strftime("%d-%b-%Y")
            )

        current += timedelta(days=1)

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

    tracker_cols = tracker_format.split("\t")

    def get_value(column):

        col = clean(column).lower()

        # Exact/priority matching
        if col in {
            "candidate name",
            "resource name",
            "name",
            "resource name (as per pan card)"
        }:
            return name

        if (
            "contact number" in col
            or col in {"contact", "phone", "mobile"}
        ):
            return phone

        if (
            "email id" in col
            or col == "email"
            or "email" == col
        ):
            return email

        if (
            col == "skill"
            or col == "skills"
            or "primary skill" in col
            or "skill name" in col
        ):
            return ", ".join(skill_list)

        if (
            "total exp" in col
            or "total experience" in col
        ):
            return exp

        if (
            "relevant exp" in col
            or "relevant experience" in col
        ):
            return exp

        if "current location" in col:
            return location

        if (
            "preferred location" in col
            or col.startswith("pref")
            or "relocation" in col
        ):
            return pref_location

        if (
            "dob" in col
            or "date of birth" in col
            or "birth" in col
        ):
            return dob

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

    if not email_text.strip():

        st.warning(
            "Please paste candidate Email / Naukri / Resdex data."
        )

        st.stop()

    # --------------------------------------------------------
    # Extract
    # --------------------------------------------------------

    data = auto_extract(email_text)

    # --------------------------------------------------------
    # Name
    # --------------------------------------------------------

    name = clean(
        data.get("Full Name", "")
    )

    # --------------------------------------------------------
    # Phone
    # --------------------------------------------------------

    # Manual override gets highest priority.
    phone = valid_phone(
        manual_phone
    )

    if not phone:

        phone = valid_phone(
            data.get("Contact Number", "")
        )

    # Final fallback
    if not phone:

        phone = first_phone(
            normalize_input(email_text)
        )

    # --------------------------------------------------------
    # Email
    # --------------------------------------------------------

    email = valid_email(
        data.get("Email ID", "")
    )

    # --------------------------------------------------------
    # Location
    # --------------------------------------------------------

    location = clean(
        data.get("Current Location", "")
    )

    pref_location = clean(
        data.get("Preferred Location", "")
    )

    # --------------------------------------------------------
    # Experience
    # --------------------------------------------------------

    exp_raw = clean(
        data.get("Experience", "")
    )

    exp = format_experience(
        exp_raw
    )

    # Example:
    # 4y 7m -> 4.7 years

    # --------------------------------------------------------
    # DOB
    # --------------------------------------------------------

    dob = clean(
        data.get("Date of Birth", "")
    )

    mmdd = get_mmdd(
        dob
    )

    # --------------------------------------------------------
    # Skills
    # --------------------------------------------------------

    skills_raw = data.get(
        "Skills",
        ""
    )

    skill_list = extract_top_skills(
        skills_raw
    )

    while len(skill_list) < 3:
        skill_list.append(" ")

    skill_list = skill_list[:3]

    # --------------------------------------------------------
    # Notice / Offer / Reason
    # --------------------------------------------------------

    notice_period = clean(
        data.get("Notice Period", "")
    )

    offer = clean(
        data.get("Offers", "")
    )

    reason = clean(
        data.get("Reason", "")
    )

    # Defaults only if not available
    if not notice_period:
        notice_period = "Immediate"

    if not offer:
        offer = "No"

    if not reason:
        reason = "Career Growth"

    # --------------------------------------------------------
    # Interview dates
    # --------------------------------------------------------

    dates, now = get_interview_dates()

    time_slot = "10:00AM-06:00PM"

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    missing_fields = []

    if not name:
        missing_fields.append("Candidate Name")

    if not phone:
        missing_fields.append("Contact Number")

    if not email:
        missing_fields.append("Email ID")

    if not location:
        missing_fields.append("Current Location")

    if not exp:
        missing_fields.append("Experience")

    if not dob:
        missing_fields.append("Date of Birth")

    if missing_fields:

        st.warning(
            "⚠️ Missing / unverified fields: "
            + ", ".join(missing_fields)
        )

        st.info(
            "If Naukri shows 'View phone number', "
            "enter the actual candidate number in the "
            "'Candidate Contact Number' box above."
        )

    # --------------------------------------------------------
    # Show extracted data before generating
    # --------------------------------------------------------

    st.subheader(
        "🔎 Extracted Candidate Details"
    )

    col1, col2 = st.columns(2)

    with col1:

        st.write(
            f"**Name:** {name or 'Not Found'}"
        )

        st.write(
            f"**Contact:** {phone or 'Not Found'}"
        )

        st.write(
            f"**Email:** {email or 'Not Found'}"
        )

        st.write(
            f"**Current Location:** "
            f"{location or 'Not Found'}"
        )

        st.write(
            f"**Preferred Location:** "
            f"{pref_location or 'Not Found'}"
        )

    with col2:

        st.write(
            f"**Experience:** "
            f"{exp or 'Not Found'}"
        )

        st.write(
            f"**DOB:** "
            f"{dob or 'Not Found'}"
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

    # --------------------------------------------------------
    # DOCX
    # --------------------------------------------------------

    try:

        doc = DocxTemplate(
            "tcs_template.docx"
        )

    except Exception as e:

        st.error(
            "❌ Could not open tcs_template.docx"
        )

        st.exception(e)

        st.stop()

    # --------------------------------------------------------
    # Template context
    # --------------------------------------------------------

    context = {

        "NAME": name,

        "CONTACT_NUMBER": phone,

        "EMAIL_ID": email,

        "CURRENT_LOCATION": location,

        "PREFERRED_LOCATION": pref_location,

        "SKILL1": skill_list[0],

        "SKILL2": skill_list[1],

        "SKILL3": skill_list[2],

        # All experience fields now receive:
        # 4.7 years
        "EXP1": exp,
        "EXP2": exp,
        "EXP3": exp,

        "NOTICE_PERIOD": notice_period,

        "OFFER": offer,

        "RELOCATION": (
            pref_location
            if pref_location
            else location
        ),

        "REASON": reason,

        "DOB": dob,

        "NEXT_DATE1": dates[0],

        "NEXT_DATE2": dates[1],

        "NEXT_DATE3": dates[2],

        "TIME": time_slot,
    }

    # --------------------------------------------------------
    # Render
    # --------------------------------------------------------

    try:

        doc.render(
            context
        )

    except Exception as e:

        st.error(
            "❌ Error while rendering the Word template."
        )

        st.exception(e)

        st.stop()

    # --------------------------------------------------------
    # FILE NAME
    # --------------------------------------------------------

    safe_name = re.sub(
        r"[^A-Za-z0-9]",
        "",
        name
    )

    if not safe_name:
        safe_name = "Candidate"

    # Example:
    # Nuthan + 0916
    #
    # Result:
    # PTN_IN_RGSID_Nuthan0916.docx

    file_name = (
        f"PTN_IN_RGSID_{safe_name}{mmdd}.docx"
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    try:

        doc.save(
            file_name
        )

    except Exception as e:

        st.error(
            "❌ Could not save generated Word file."
        )

        st.exception(e)

        st.stop()

    # --------------------------------------------------------
    # Download
    # --------------------------------------------------------

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

    critical_missing = []

    if not name:
        critical_missing.append("Name")

    if not phone:
        critical_missing.append("Contact Number")

    if not email:
        critical_missing.append("Email ID")

    if not location:
        critical_missing.append("Current Location")

    if not exp:
        critical_missing.append("Experience")

    if not dob:
        critical_missing.append("DOB")

    if len(skill_list) < 3:
        critical_missing.append("Skills")


    if critical_missing:

        st.error(
            "❌ Profile was NOT generated because these fields "
            "could not be verified: "
            + ", ".join(critical_missing)
        )

        st.stop()

    else:

        st.success(
            f"✅ Profile Generated Successfully: {file_name}"
        )

    # --------------------------------------------------------
    # Tracker
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Final generated values
    # --------------------------------------------------------

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
        f"**Experience:** {exp}"
    )

    st.write(
        f"**DOB:** {dob}"
    )

    st.write(
        f"**Interview Dates:** "
        f"{dates[0]}, {dates[1]}, {dates[2]}"
    )

    st.write(
        f"**Time Slot:** {time_slot}"
    )
