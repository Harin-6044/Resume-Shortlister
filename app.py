import os
import io
import json
import fitz
import docx
import streamlit as st
import google.generativeai as genai
from models import CandidateAnalysis
from dotenv import load_dotenv

load_dotenv()

try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

except (FileNotFoundError, KeyError):
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

PROMPT_TEMPLATE = """
You are a highly intelligent AI-powered Technical Recruiter. 
Your primary goal is to dynamically adapt your expertise to match the specific role described in the provided Job Description. 
You must act as a specialist for whatever role is presented to you.

Instructions:
1.  Determine Key Criteria: First, carefully analyze the provided 'Job Description' to identify the 5-7 most critical skills, technologies and qualifications required for the role. This set of criteria becomes your evaluation rubric. Do not use a generic software engineering rubric, it must be tailored to the specific job.
2.  Analyze the Resume against Criteria: Next, thoroughly review the candidate's 'Resume Text'. Scrutinize their experience, projects and listed skills to find evidence of the key criteria you identified in step 1.
3.  Score and Justify: Based on how well the resume aligns with the key criteria, provide a holistic fit score from 0 to 100. Your reasoning must clearly connect the resume's content (or lack thereof) to the job description's specific requirements.
4.  Maintain Objectivity: Base your entire analysis strictly on the information given in the resume and the job description. Do not invent or infer details.
5.  JSON Output Only: Your entire response must be a single, valid JSON object. Do not include any text, explanations or markdown formatting before or after the JSON object.

Job Description:
<job_description>
{job_description}
</job_description>

Resume Text:
<resume_text>
{resume_text}
</resume_text>

Required JSON Output Format:
{{
    "candidate_name": "Full Name",
    "score": <integer from 0-100>,
    "summary": "A 2-3 sentence summary of the candidate's overall fit for this specific role.",
    "reasoning": "A single string containing a detailed analysis in markdown format. It must start with '**Strengths:**' followed by bullet points and then '**Gaps:**' followed by bullet points. For example: '**Strengths:**\\n- 5+ years of Java experience.\\n- Experience with REST APIs and SQL.\\n\\n**Gaps:**\\n- Lacks experience with cloud platforms (AWS/GCP) mentioned in the JD.'",
    "is_recommended": <boolean, true if score >= 70, else false>
}}
"""

def parse_resume(file_bytes, filename) -> str:
    text = ""
    try:
        if filename.endswith(".pdf"):
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                text = "".join(page.get_text() for page in doc)
        elif filename.endswith(".docx"):
            doc = docx.Document(io.BytesIO(file_bytes))
            text = "\n".join(para.text for para in doc.paragraphs)
    
    except Exception as e:
        st.error(f"Error parsing {filename} : {e}")
    return text

def analyze_with_gemini(job_description: str, resume_text: str) -> CandidateAnalysis:
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    prompt = PROMPT_TEMPLATE.format(job_description=job_description, resume_text=resume_text)

    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip().replace("```json", "").replace("```", "")
        response_json = json.loads(response_text)

        if isinstance(response_json.get('reasoning'), dict):
            reasoning_dict = response_json['reasoning']
            strengths = reasoning_dict.get('Strengths', 'N/A')
            gaps = reasoning_dict.get('Gaps', 'N/A')
            response_json['reasoning'] = f"\n**Strengths:**\n{strengths}\n\n**Gaps:**\n{gaps}"

        return CandidateAnalysis(**response_json)

    except (json.JSONDecodeError, TypeError, KeyError) as e:
        st.error(f"Error parsing Gemini's JSON response : {e}, the model might have returned an invalid format !")
        return CandidateAnalysis(
            candidate_name="Unknown/Error", score=0, summary="Analysis failed due to response format error !",
            reasoning=f"Failed to parse model output, raw response : {response.text}", is_recommended=False
        )
    except Exception as e:
        st.error(f"An unexpected error occurred during analysis : {e}")
        return CandidateAnalysis(
            candidate_name="Unknown/Error", score=0, summary="Analysis failed !",
            reasoning=f"An unexpected error occurred : {str(e)}", is_recommended=False
        )

st.set_page_config(page_title="Resume Shortlister", page_icon="🤖", layout="wide")

st.title("Resume Shortlister")
st.markdown("I’m Max and I instantly rank candidates to accelerate your hiring process.")

st.sidebar.header("How to Use")
st.sidebar.info(
    "1. Paste the Job Description into the text area.\n"
    "2. Upload Resumes (PDF or DOCX).\n"
    "3. Click 'Analyze' to start the process.\n"
    "4. Review the ranked results."
)
st.sidebar.warning("Note: Your data is not stored and the analysis is performed in real-time.")

jd_input = st.text_area("Paste the Job Description here", height=200)
resume_files = st.file_uploader(
    "Upload Candidate Resumes",
    type=["pdf", "docx"],
    accept_multiple_files=True
)

if st.button("Analyze", type="primary"):
    if not jd_input.strip():
        st.error("Please paste a job description.")
    elif not resume_files:
        st.error("Please upload at least one resume.")
    else:
        with st.spinner("Analyzing ... this may take a few moments ..."):
            all_analyses = []
            progress_bar = st.progress(0)
            
            for i, file in enumerate(resume_files):
                st.write(f"Processing {file.name} ...")
                file_bytes = file.read()
                resume_text = parse_resume(file_bytes, file.name)
                
                if resume_text:
                    analysis = analyze_with_gemini(jd_input, resume_text)
                    all_analyses.append(analysis)
                
                progress_bar.progress((i + 1) / len(resume_files))

            progress_bar.empty()

            if all_analyses:
                ranked_candidates = sorted(all_analyses, key=lambda x: x.score, reverse=True)
                
                st.subheader("Analysis Results")
            
                for candidate in ranked_candidates:
                    expander_title = f"**{candidate.candidate_name}**"
                    
                    with st.expander(expander_title, expanded=False):
                        score_color = "green" if candidate.is_recommended else "orange"
                        score_html = f"**Score:** <span style='color:{score_color}; font-size: 1.1em;'>{candidate.score}/100</span>"
                        st.markdown(score_html, unsafe_allow_html=True)

                        if candidate.is_recommended:
                            st.success("Recommended for Interview")
                        else:
                            st.warning("Review with Caution")
                        
                        st.markdown("**Summary:**")
                        st.markdown(candidate.summary)