
import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from streamlit_app.components.sidebar import render_sidebar
from streamlit_app.components.chat_interface import render_chat_interface
from streamlit_app.components.debug_panel import render_debug_panel
from streamlit_app.core.session_manager import initialize_session_state
from streamlit_app.utils.page_config import setup_page_config


def main():
    """Main application entry point"""
    
    # Configure page
    setup_page_config()
    
    # Initialize session state
    initialize_session_state()
    
    # Render sidebar
    render_sidebar()
    
    # Main content area
    st.title("🏥 Medical Knowledge Graph Agent")
    st.markdown("---")
    
    # Render main chat interface
    render_chat_interface()
    
    # Debug panel (collapsible)
    if st.session_state.get("show_debug", False):
        st.markdown("---")
        render_debug_panel()


if __name__ == "__main__":
    main()
