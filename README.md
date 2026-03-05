# 4300 Flask Template

## Contents

- [Summary](#summary)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Deploying on the Server](#deploying-on-the-server)
- [Running Locally](#running-locally)
- [Troubleshooting Deployment Issues](#troubleshooting-deployment-issues)
- [Virtual Environments and Dependency Tracking](#virtual-environments-and-dependency-tracking)
- [Additional Resources](#additional-resources)
- [Feedback and Support](#feedback-and-support)

## Summary

This is a **Flask** template for **CS/INFO 4300 class at Cornell University**

This template provides:
- **Backend**: Flask with SQLite database and SQLAlchemy ORM
- **Frontend**: Server-rendered HTML templates with static assets

You will use this template to directly deploy your Flask code on the project server.

After you follow the steps below, you should have set up a public address dedicated to your team's project. For the moment, a template app will be running. In future milestones you will be updating the code to replace that template with your very own app.


## Quick Start

For the fastest way to get started with development:

### Windows
```bash
# 1. Set up Python virtual environment
python -m venv venv
venv\Scripts\activate

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Start Flask
python src/app.py
```

### Mac/Linux
```bash
# 1. Set up Python virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Start Flask
python src/app.py
```

Then open `http://localhost:5001` in your browser!

## Architecture

```
4300-Flask-Template/
├── src/
│   ├── app.py          # Flask app entry point
│   ├── models.py       # SQLAlchemy database models
│   ├── routes.py       # Search routes (+ USE_LLM toggle)
│   ├── llm_routes.py   # LLM chat route (only used when USE_LLM = True)
│   ├── init.json       # Seed data
│   ├── static/         # CSS, images
│   └── templates/
│       ├── base.html   # Simple search page
│       └── chat.html   # Search + AI chat page (USE_LLM = True)
├── requirements.txt
├── Dockerfile
└── .env                # API_KEY goes here (not committed)
```

- **Database**: SQLite with SQLAlchemy ORM

## Deploying on the server

For the initial deployment, only one member of your team needs to follow the steps below.

### Step 0: Fork this template

- **Fork** this repository on your GitHub account
- Make sure your repository is set to **PUBLIC** (required for deployment)
- Keep in mind that other students may be able to see your repository

### Step 1: Login to the deployment dashboard

- Login to the dashboard at https://4300showcase.infosci.cornell.edu/login using the Google account associated with your Cornell Email/NetID. Click the "INFO 4300: Language Information" **Spring 2026** course in the list of course offerings.

![Project Server Home](assets/server-home.png)

### Step 2: Navigate to Your Team Dashboard

- You'll see a list of all teams in the course
- Find your team and click **"Dashboard"** to go to your team's deployment dashboard

![Teams Page For a Course](assets/teams.png)

### Step 3: Deploy Your Project

You'll see your team's dashboard that looks like this:

![Team Dashboard](assets/dashboard-new.png)

1. **Add Your GitHub URL** — paste the URL of your forked (public) repository
2. **Click "Deploy"** — this clones your code, builds the Docker container, and starts your app
3. **Click "Open Project"** once the status updates to visit your live app

Expand **"Build Logs"** or **"Container Logs"** if something goes wrong.

#### Redeploying After Updates

Push changes to GitHub, then click **"Deploy"** again.

## Running locally

### Prerequisites
- **Python 3.10 or above**

### Setup and Run

1. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the app:
   ```bash
   python src/app.py
   ```

   Open `http://localhost:5001` in your browser.

### Modifying the Data

Edit `src/init.json` to replace the dummy episode data with your own. You can add additional data files as needed.

## Troubleshooting Deployment Issues

### My app isn't loading after deployment
- Wait 30–60 seconds after deployment — larger apps need time to start up
- Try refreshing your browser or clicking **"Open Project"** again

### How do I see what went wrong?
- **Build Logs** — errors during the Docker build (dependency issues, etc.)
- **Container Logs** — runtime errors from your running application
- Common causes:
  - Missing packages in `requirements.txt`
  - Malformed `src/init.json`

### Login/Authentication Issues
- If you get a 401 error, try logging out and back in with your Cornell email

### Still Having Issues?
Post on Ed Discussion with your team name, what you tried, and screenshots of error logs.

## Virtual Environments and Dependency Tracking

Keep your virtual environment out of git — it inflates repository size and will break deployment.

1. Make sure `venv/` (or whatever you named it) is listed in `.gitignore`
2. If you already committed it, untrack it with `git rm -r --cached venv/`
3. When you install new packages, update `requirements.txt`:
   ```bash
   pip freeze > requirements.txt
   ```

## Additional Resources

📋 **Known Issues Database**: https://docs.google.com/document/d/1sF2zsubii_SYJLfZN02UB9FvtH1iLmi9xd-X4wbpbo8

## Feedback and Support

- **Problems with deployment?** Post on Ed Discussion or email course staff
- **Questions about the deployment system?** Course staff are happy to help!
