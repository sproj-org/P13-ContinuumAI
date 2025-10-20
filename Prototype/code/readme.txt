CONTINUUMAI APPLICATION SETUP GUIDE (FINAL)
===========================================
(For projects with separate requirements files for components)

This guide details the steps to set up and run the ContinuumAI application, which has a backend API and a Streamlit UI, using two separate requirements files.

1. NAVIGATE TO THE ROOT CODE DIRECTORY
--------------------------------------
All setup begins from the directory containing the main scripts and folders.

   cd prototype/code


2. SET UP AND ACTIVATE THE VIRTUAL ENVIRONMENT
--------------------------------------------
A single virtual environment will be used for both components.

A. Create the Environment (First Time Only)

   - On macOS/Linux:
     python3 -m venv venv
   - On Windows:
     python -m venv venv

B. Activate the Environment (Required for every new session)

   - On macOS/Linux:
     source venv/bin/activate
   - On Windows:
     .\venv\Scripts\activate


3. INSTALL ALL DEPENDENCIES
---------------------------
Install packages from both requirements files into the single activated virtual environment. This step is only required once. 
Make sure your environment is activated before u do this!

A. Install General/Frontend Requirements (from 'prototype/code'):

   pip install -r requirements.txt

B. Install Backend API Requirements (from 'prototype/code'):

   pip install -r backend/api/requirements.txt


4. RUN THE APPLICATION COMPONENTS
---------------------------------
The backend and Streamlit UI must run concurrently in SEPARATE terminal windows. Ensure the virtual environment is activated in both terminals.

4.1. Start the Backend API (Terminal 1)

   cd backend/api
   python main.py

4.2. Start the Streamlit UI (Terminal 2)

   Note: Ensure Terminal 2 is back in the 'prototype/code' directory.

   streamlit run frontend/app.py


IMPORTANT NOTES:
----------------
* ORDER MATTERS: Start the Backend API first (4.1) before starting the Streamlit UI (4.2).
* DEPENDENCIES: Once installed in Step 3, all packages are available to both components running in the activated 'venv'.