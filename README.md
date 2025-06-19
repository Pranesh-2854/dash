# Jira Dashboard

A web dashboard for managing Jira filters, roles, and issues, with Excel integration and interactive visualisations.

---

## Features

- Interactive Dashboard Visualizations
- Create/update Jira filters
- Delete issues by filter or issue key
- Manage project roles (viewer/editor)
- Refresh and export Jira data to Excel
- Responsive frontend (HTML/JS)
- Python Flask backend

---

## Requirements

- Python 3.8+
- pip
- Jira account with API access
- [Git](https://git-scm.com/) (for deployment)
- [Render.com](https://render.com/) account (for deployment)

---

## Local Setup

1. **Clone the repository**
   ```sh
   git clone https://github.com/yourusername/your-repo.git
   cd your-repo
   ```

2. **Create and configure your `.env` file**
   - Copy `.env.example` to `.env` and fill in your Jira credentials:
     ```
     JIRA_DOMAIN=yourcompany.atlassian.net
     JIRA_EMAIL=your@email.com
     JIRA_API_TOKEN=your_api_token
     ```

3. **Install dependencies**
   ```sh
   pip install -r backend/requirements.txt
   ```

4. **Ensure your Excel file is in the backend directory**
   - Place `data.xlsx` in `backend/` (or update the path in the code).

5. **Run the Flask backend**
   ```sh
   cd backend
   python app.py
   ```
   - The backend will run at [http://localhost:5000](http://localhost:5000).

6. **Open the frontend**
   - Open `frontend/index.html` (or `func.html`) in your browser.
   - If you want to serve the frontend via Flask, add a static file route in `app.py`.

---

## Deploying on Render

1. **Push your code to GitHub**
   ```sh
   git add .
   git commit -m "Ready for deployment"
   git push origin main
   ```

2. **Create a new Web Service on Render**
   - Go to [Render.com](https://render.com/), log in, and click "New +" → "Web Service".
   - Connect your GitHub repo.
   - **Do not set a root directory** (leave it as the repo root).
   - **Build Command:**  
     ```
     pip install -r backend/requirements.txt
     ```
   - **Start Command:**  
     ```
     gunicorn backend.app:app
     ```
     - This tells Gunicorn to look for `app` in `backend/app.py`.

3. **Add environment variables**
   - In the Render dashboard, add:
     - `JIRA_DOMAIN`
     - `JIRA_EMAIL`
     - `JIRA_API_TOKEN`

4. **(Optional) Add a Render Disk for persistent Excel storage**
   - In the dashboard, add a Disk (e.g., 1GB, mount path `/data`).
   - Update your code to use `/data/data.xlsx` as the Excel path.

5. **Deploy**
   - Render will build and deploy your app.
   - Visit your Render URL to use the dashboard.

6. **Frontend**
   - You can serve the frontend via Flask or host it separately (e.g., Netlify, Vercel).
   - If hosting separately, update API URLs in your JS to point to your Render backend.

---

## Notes

- **Excel file changes are server-local**: All edits via the dashboard update the server’s copy of `data.xlsx`.
- **For always-on service**, use a paid Render plan (free tier may sleep after inactivity).

---

## Troubleshooting

- **Jira errors**: Check your `.env` values and Jira permissions.
- **Excel errors**: Ensure `data.xlsx` exists and is writable by the server.
- **Deployment issues**: Check Render logs for errors and verify environment variables.

---

## License

MIT
