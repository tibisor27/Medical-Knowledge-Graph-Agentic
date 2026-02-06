import streamlit as st

def setup_page_config():
    """Configure Streamlit page settings"""
    st.set_page_config(
        page_title="Medical Knowledge Graph Agent",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={
            'Get Help': None,
            'Report a bug': None,
            'About': "# Medical Knowledge Graph Agent\nAI-powered medical information assistant."
        }
    )
    
    # Custom CSS
    st.markdown("""
        <style>
        /* Force light theme colors */
        .stChatMessage {
            padding: 1rem;
            border-radius: 0.5rem;
            margin-bottom: 1rem;
            color: #1f1f1f !important;  /* <-- ADAUGĂ ASTA */
        }
        
        /* User messages */
        .stChatMessage[data-testid="user-message"] {
            background-color: #e3f2fd;
            color: #0d47a1 !important;  /* <-- ȘI ASTA */
        }
        
        /* Assistant messages */
        .stChatMessage[data-testid="assistant-message"] {
            background-color: #f5f5f5;
            color: #212121 !important;  /* <-- ȘI ASTA */
        }
        
        /* Force text color in main container */
        .main .block-container {
            color: #1f1f1f !important;
        }
        
        /* Sidebar text */
        .css-1d391kg, [data-testid="stSidebar"] {
            padding-top: 2rem;
            color: #e0e0e0 !important;
        }
        
        /* Button styling */
        .stButton>button {
            width: 100%;
            border-radius: 0.5rem;
            padding: 0.5rem 1rem;
            color: #1f1f1f !important;
        }
        
        /* Info boxes */
        .info-box {
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #e8f4f8;
            border-left: 4px solid #2196F3;
            margin: 1rem 0;
            color: #01579b !important;
        }
        
        /* Warning boxes */
        .warning-box {
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #fff3e0;
            border-left: 4px solid #ff9800;
            margin: 1rem 0;
            color: #e65100 !important;
        }
        
        /* Success boxes */
        .success-box {
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #e8f5e9;
            border-left: 4px solid #4caf50;
            margin: 1rem 0;
            color: #1b5e20 !important;
        }
        
        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)