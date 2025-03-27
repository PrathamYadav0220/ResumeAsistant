import streamlit as st
# Set page config first, before any other st commands
st.set_page_config(page_title="ResumeATS Pro", layout="wide")

import os
from dotenv import load_dotenv
import google.generativeai as genai
from PyPDF2 import PdfReader
import re
from collections import Counter
import hashlib
import plotly.graph_objects as go
import numpy as np
from database import init_db, create_user, verify_user

# Custom CSS for Apple-inspired design
st.markdown("""
    <style>
    .main {
        background-color: #f5f5f7;
        color: #1d1d1f;
    }
    .stButton>button {
        background-color: #0071e3;
        color: white;
        border-radius: 20px;
    }
    .stProgress > div > div {
        background-color: #0071e3;
    }
    .stTextInput>div>div>input {
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize database
init_db()

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None

# Authentication UI
def show_auth_ui():
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        st.header("Login")
        login_username = st.text_input("Username", key="login_username")
        login_password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            if verify_user(login_username, login_password):
                st.session_state.authenticated = True
                st.session_state.username = login_username
                st.success("Successfully logged in!")
                st.rerun()
            else:
                st.error("Invalid username or password")

    with tab2:
        st.header("Sign Up")
        new_username = st.text_input("Username", key="new_username")
        new_email = st.text_input("Email", key="new_email")
        new_password = st.text_input("Password", type="password", key="new_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
        
        if st.button("Sign Up"):
            if new_password != confirm_password:
                st.error("Passwords do not match")
            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters long")
            else:
                if create_user(new_username, new_password, new_email):
                    st.success("Account created successfully! Please login.")
                else:
                    st.error("Username or email already exists")

# Main app logic
if not st.session_state.authenticated:
    show_auth_ui()
else:
    # Show logout button in sidebar
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.rerun()
        
    st.title(f"Welcome {st.session_state.username}!")
    
    # Add feature selector
    feature = st.selectbox(
        "Select Feature",
        ["Resume ATS Pro", "Auto Apply", "Resume Generation"],
        index=0
    )
    
    if feature == "Resume ATS Pro":
        st.title("ResumeATS Pro")
        st.subheader("Optimize Your Resume for ATS and Land Your Dream Job")
        
        # Load environment variables and configure API
        load_dotenv()
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        model = genai.GenerativeModel("gemini-2.0-flash")

        # Add new scoring helper functions
        def calculate_keyword_match(text, keywords):
            """Calculate keyword match percentage"""
            text = text.lower()
            found_keywords = sum(1 for keyword in keywords if keyword.lower() in text)
            return (found_keywords / len(keywords)) * 100 if keywords else 0

        def normalize_score(score):
            """Normalize score to prevent outliers"""
            return min(max(score, 0), 100)

        def get_cached_score(pdf_text, job_description=None):
            """Get cached score or None"""
            if not pdf_text:
                return None
            # Create unique hash for the resume and job description combination
            content_hash = hashlib.md5((pdf_text + (job_description or "")).encode()).hexdigest()
            return st.session_state.get(f'score_{content_hash}')

        def cache_score(pdf_text, score, job_description=None):
            """Cache the score"""
            content_hash = hashlib.md5((pdf_text + (job_description or "")).encode()).hexdigest()
            st.session_state[f'score_{content_hash}'] = score

        class ATSScoreComponents:
            def __init__(self):
                self.format_score = 0
                self.content_score = 0
                self.keyword_score = 0
                self.match_score = 0
                self.total_score = 0

        def calculate_base_ats_score(pdf_text, job_description=None):
            """Calculate unified ATS score and return components"""
            score_components = ATSScoreComponents()
            
            # Basic Resume Structure (40 points)
            sections = ['experience', 'education', 'skills']
            for section in sections:
                if section in pdf_text.lower():
                    score_components.format_score += 10
            
            # Clean formatting check
            if len(re.findall(r'[^\x00-\x7F]', pdf_text)) == 0:
                score_components.format_score += 5
            if len(re.findall(r'[^\S\n]{2,}', pdf_text)) == 0:
                score_components.format_score += 5

            # Content Quality
            action_verbs = ['achieved', 'implemented', 'developed', 'managed', 'created', 'increased']
            score_components.keyword_score = calculate_keyword_match(pdf_text, action_verbs)
            score_components.content_score = score_components.keyword_score * 0.2

            # Job description matching
            if job_description:
                job_terms = set(re.findall(r'\b\w+\b', job_description.lower()))
                resume_terms = set(re.findall(r'\b\w+\b', pdf_text.lower()))
                score_components.match_score = len(job_terms.intersection(resume_terms)) / len(job_terms) * 30
                score_components.content_score += score_components.match_score
            else:
                score_components.content_score += 30 if len(pdf_text.split()) > 200 else 15

            score_components.total_score = normalize_score(score_components.format_score + score_components.content_score)
            return score_components

        def display_score_visualization(score_components, analysis_components):
            """Display visual representation of ATS score"""
            ats_score = score_components.total_score
            
            # Single consistent score display
            st.markdown(f"### ATS Compatibility Score: {ats_score:.1f}/100")
            st.progress(ats_score/100)
            
            # Create radar chart for components
            categories = list(analysis_components.keys())
            values = list(analysis_components.values())
            
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=values,
                theta=categories,
                fill='toself',
                name='Score Components'
            ))
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 100]
                    )
                ),
                showlegend=False,
                title="Score Component Breakdown",
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)

        def get_gemini_output(pdf_text, prompt):
            """Enhanced Gemini output with score visualization"""
            cached_score = get_cached_score(pdf_text, prompt)
            if cached_score:
                return cached_score
            
            score_components = calculate_base_ats_score(pdf_text, job_description if use_jd else None)
            
            try:
                response = model.generate_content([pdf_text, prompt])
                response_text = response.text
                
                # Calculate component scores
                analysis_components = {
                    'Resume Structure': normalize_score(score_components.format_score * 2.5),
                    'Content Quality': normalize_score(score_components.content_score * 1.67),
                    'Keyword Match': score_components.keyword_score
                }
                
                if use_jd:
                    analysis_components['Job Description Match'] = normalize_score(score_components.match_score * 3.33)
                
                # Display visualization with consistent scoring
                display_score_visualization(score_components, analysis_components)
                
                enhanced_response = f"""
        Score Summary:
        ATS Compatibility Score: {score_components.total_score:.1f}/100

        Detailed Analysis:
        {response_text}
        """
                cache_score(pdf_text, enhanced_response, prompt)
                return enhanced_response
                
            except Exception as e:
                st.error(f"Error in generating response: {str(e)}")
                return None

        # Initialize session state for caching if not exists
        if 'score_cache' not in st.session_state:
            st.session_state.score_cache = {}

        # Function to read PDF
        def read_pdf(uploaded_file):
            if uploaded_file is not None:
                pdf_reader = PdfReader(uploaded_file)
                pdf_text = ""
                for page in pdf_reader.pages:
                    pdf_text += page.extract_text()
                return pdf_text
            else:
                raise FileNotFoundError("No file uploaded")

        # Streamlit UI
        st.title("ResumeATS Pro")
        st.subheader("Optimize Your Resume for ATS and Land Your Dream Job")

        # File upload
        upload_file = st.file_uploader("Upload your resume (PDF)", type=["pdf"])

        # Job description toggle and input
        st.markdown("### 📋 Job Description Analysis")
        use_jd = st.checkbox("Include job description for targeted analysis")
        job_description = ""
        if use_jd:
            job_description = st.text_area("Enter the job description", height=200)
            st.info("💡 Paste the complete job description for more accurate matching and ATS scoring")

        # Analysis options
        analysis_option = st.radio("Choose analysis type:", 
                                ["Quick Scan", "Detailed Analysis", "ATS Optimization"])

        if st.button("Analyze Resume"):
            if upload_file is not None:
                pdf_text = read_pdf(upload_file)
                
                if analysis_option == "Quick Scan":
                    prompt = f"""
                    Analyze this resume and provide:
                    1. Key strengths (3-4 points)
                    2. Critical improvements needed (2-3 points)
                    3. Keyword optimization suggestions
                    
                    Focus on actionable feedback without numerical scores.
                    
                    Resume text: {pdf_text}
                    {f'Job Description: {job_description}' if use_jd else ''}
                    """

                elif analysis_option == "Detailed Analysis":
                    prompt = f"""
                    You are an expert ATS analyzer. Provide a comprehensive analysis:

                    {f'''Job Alignment Analysis (40 points):
                    1. Required Skills Coverage (15 points):
                    - Must-have skills presence
                    - Nice-to-have skills presence
                    - Technology stack matching
                    
                    2. Experience Match (15 points):
                    - Years of experience alignment
                    - Role responsibility matching
                    - Industry-specific requirements
                    
                    3. Qualification Match (10 points):
                    - Education requirements
                    - Certification requirements
                    - Special qualification matching''' if use_jd else ''}

                    Technical ATS Analysis (60 points):
                    1. Keyword Optimization (20 points):
                    - Industry-standard terminology
                    - Technical skill formatting
                    - Keyword density and placement
                    
                    2. Format & Structure (20 points):
                    - Section header standardization
                    - Consistent formatting
                    - ATS-friendly layout
                    
                    3. Content Quality (20 points):
                    - Quantified achievements
                    - Role-specific accomplishments
                    - Professional impact metrics

                    Provide:
                    1. Category-wise scoring with justification
                    2. {'Job fitness score and' if use_jd else ''} ATS compatibility score
                    3. Detailed keyword analysis
                    4. Section-by-section improvement recommendations
                    5. Format optimization guide
                    
                    Resume text: {pdf_text}
                    {f'Job Description: {job_description}' if use_jd else ''}
                    """

                else:  # ATS Optimization
                    prompt = f"""
                    You are an expert ATS optimization specialist. Analyze with enhanced criteria:

                    {f'''Job-Specific Optimization (50 points):
                    1. Key Requirements Match (20 points):
                    - Must-have skills coverage
                    - Experience level alignment
                    - Industry-specific keywords
                    
                    2. Role Alignment (20 points):
                    - Job title optimization
                    - Responsibility matching
                    - Achievement relevance
                    
                    3. Qualification Alignment (10 points):
                    - Education requirements
                    - Certification matches
                    - Special requirements''' if use_jd else ''}

                    Technical Optimization (50 points):
                    1. Keyword Placement (20 points):
                    - Strategic keyword distribution
                    - Contextual usage
                    - Natural integration
                    
                    2. Format Optimization (15 points):
                    - ATS-friendly sections
                    - Consistent structure
                    - Clean formatting
                    
                    3. Content Enhancement (15 points):
                    - Achievement metrics
                    - Role descriptions
                    - Skill demonstrations

                    Provide:
                    1. Detailed optimization score
                    2. {'Job-specific keyword recommendations and' if use_jd else ''} general keywords
                    3. Section-wise formatting improvements
                    4. Content enhancement suggestions
                    5. Priority action items
                    
                    Resume text: {pdf_text}
                    {f'Job Description: {job_description}' if use_jd else ''}
                    """
                
                response = get_gemini_output(pdf_text, prompt)
                
                st.subheader("Analysis Results")
                st.write(response)
                
                # Option to chat about the resume
                st.subheader("Have questions about your resume?")
                user_question = st.text_input("Ask me anything about your resume or the analysis:")
                if user_question:
                    chat_prompt = f"""
                    Based on the resume and analysis above, answer the following question:
                    {user_question}
                    
                    Resume text: {pdf_text}
                    Previous analysis: {response}
                    """
                    chat_response = get_gemini_output(pdf_text, chat_prompt)
                    st.write(chat_response)
            else:
                st.error("Please upload a resume to analyze.")

        # Additional resources
        st.sidebar.title("Resources")
        st.sidebar.markdown("""
        - [Resume Writing Tips](https://www.jobbank.gc.ca/findajob/resources/write-good-resume)
        - [ATS Optimization Guide](https://career.io/career-advice/create-an-optimized-ats-resume)
        - [Interview Preparation](https://hbr.org/2021/11/10-common-job-interview-questions-and-how-to-answer-them)
        """)

        # Feedback form
        st.sidebar.title("Feedback")
        st.sidebar.text_area("Help us improve! Leave your feedback:")
        st.sidebar.button("Submit Feedback")
        
    elif feature == "Auto Apply":
        st.title("Auto Apply")
        st.subheader("Automatically Apply to Jobs")
        st.info("🚧 This feature is coming soon! Stay tuned for updates.")
        
    elif feature == "Resume Generation":
        st.title("Resume Generation")
        st.subheader("Generate Professional Resumes")
        st.info("🚧 This feature is coming soon! Stay tuned for updates.")
