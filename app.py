import streamlit as st
import openai
import tempfile
import psutil
import os
from dotenv import load_dotenv
import time
import PyPDF2
import docx
from PIL import Image
import pytesseract
import io
import pandas as pd

# Load environment variables (API Key)
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# Set the API key for OpenAI
openai.api_key = openai_api_key

# Display app title
st.title("Statistical Analyst AI")

# Initialize chat history if not already in session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Function to release file if locked
def release_file(file_path):
    for proc in psutil.process_iter():
        try:
            for item in proc.open_files():
                if file_path in item.path:
                    st.write(f"File {file_path} is locked by process {proc.pid}, waiting...")
                    time.sleep(1)  # Wait for file to be released
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            continue

# Function to extract text from different file types
@st.cache_data
def extract_text_from_file(file_path, file_type):
    text = ""
    try:
        if file_type == "pdf":
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = "\n".join([page.extract_text() for page in reader.pages])
        elif file_type == "docx":
            doc = docx.Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
        elif file_type == "csv":
            df = pd.read_csv(file_path)
            text = df.to_string(index=False)
        elif file_type == "txt":
            with open(file_path, "r") as f:
                text = f.read()
        elif file_type in ["jpg", "jpeg", "png"]:
            # Use OCR to extract text from images
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)
        else:
            st.error("Unsupported file type")
    except Exception as e:
        st.error(f"Error extracting text from file: {e}")
    return text

# File upload section
uploaded_file = st.file_uploader("Upload a file (PDF, TXT, CSV, DOC, DOCX, JPG, PNG)", 
                                 type=["pdf", "txt", "csv", "doc", "docx", "json", "jpg", "jpeg", "png", "pptx", "xlsx"])

# If a file is uploaded, save it temporarily
if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(uploaded_file.read())
        temp_file_path = temp_file.name

    # Before processing, check if the file is locked and release it
    release_file(temp_file_path)

    st.session_state["temp_file_path"] = temp_file_path  # Store file path in session state
    file_extension = uploaded_file.name.split('.')[-1].lower()  # Get file extension

    # Extract text from the file
    file_text = extract_text_from_file(temp_file_path, file_extension)

    # Display the extracted text (optional)
    st.write("Extracted Text Preview:")
    st.text_area("Preview", value=file_text[:1000], height=200)  # Show first 1000 chars as preview

    # Add query input section (to prevent re-uploading)
    user_query = st.text_input("Enter your query about the uploaded file (e.g., summarize the file)")

    if user_query:
        with st.spinner("Processing your request..."):
            try:
                # Combine extracted text and query for processing
                prompt = f"Here is the content from the uploaded file: {file_text}\n\nUser Query: {user_query}"

                # Use the correct method for chat models
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",  # You can change this to another model if needed
                    messages=[{"role": "system", "content": "You are a helpful assistant."},
                              {"role": "user", "content": prompt}]
                )
                # Get and display assistant's reply
                assistant_reply = response.choices[0].message["content"]
                st.session_state.messages.append({"role": "assistant", "content": assistant_reply})

                with st.chat_message("assistant"):
                    st.markdown(assistant_reply)

            except Exception as e:
                st.error(f"Failed to process query: {e}")

# User input box for general queries (without file)
user_input = st.text_input("Ask me anything about statistics...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Display user message
    with st.chat_message("user"):
        st.markdown(user_input)

    # Add the system instructions for your assistant
try:
    system_message = {
        "role": "system",
        "content": "You are a knowledgeable AI assistant specializing in solving statistical problems. You provide clear explanations, perform data analysis, interpret results, and assist with statistical software like R, Python, and SPSS. You help users with hypothesis testing, inferential statistics, regression analysis, structural equation modeling, meta-analysis, and other statistical methods."
    }

    # Create a new thread for the assistant
    thread = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # Use the appropriate model
        messages=[system_message, {"role": "user", "content": user_input}]
    )

    # Get the assistant's response
    assistant_reply = thread['choices'][0]['message']['content']

    # Append Assistant's reply to chat history
    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})

    # Display Assistant's reply
    with st.chat_message("assistant"):
        st.markdown(assistant_reply)

except Exception as e:
    st.error(f"Error with OpenAI response: {e}")
