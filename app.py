# app.py -- Fully Fixed Movie Recommender with Working Admin Dashboard
import streamlit as st
import pickle, os, hashlib, datetime, tempfile
import pandas as pd
import requests
import re

# ---------- Config / Storage Paths ----------
HOME = os.path.expanduser("~")
COMMENT_FILE = os.path.join(HOME, "movie_comments.csv")
USER_FILE = os.path.join(HOME, "movie_users.pkl")

st.set_page_config(page_title="🎬 Movie Recommender", layout="wide")

# ---------- ADMIN ACCOUNT ----------
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = hashlib.sha256("admin123".encode()).hexdigest()   # default

# ---------- Utility: atomic CSV write ----------
def atomic_write_csv(df: pd.DataFrame, path: str):
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".csv", dir=os.path.dirname(path))
    os.close(tmp_fd)
    try:
        df.to_csv(tmp_path, index=False)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise

# ---------- Comments persistence ----------
def load_comments_from_file():
    if os.path.exists(COMMENT_FILE):
        try:
            df = pd.read_csv(COMMENT_FILE)
            if set(df.columns) >= {"user", "text", "time"}:
                return df.to_dict("records")
            else:
                return []
        except Exception:
            return []
    return []

def save_comments_to_file(comments_list):
    df = pd.DataFrame(comments_list)
    atomic_write_csv(df, COMMENT_FILE)

# ---------- Users persistence ----------
def load_users():
    if os.path.exists(USER_FILE):
        try:
            with open(USER_FILE, "rb") as f:
                return pickle.load(f)
        except Exception:
            return {}
    return {}

def save_users(users_dict):
    with open(USER_FILE, "wb") as f:
        pickle.dump(users_dict, f)

# ---------- Password hashing ----------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ---------- Initialize stored data ----------
CREDENTIALS = load_users()

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ""
if 'is_admin' not in st.session_state:
    st.session_state['is_admin'] = False
if 'comments' not in st.session_state:
    st.session_state['comments'] = load_comments_from_file()
if 'last_recommendations' not in st.session_state:
    st.session_state['last_recommendations'] = {"movies": [], "posters": []}
if "show_admin" not in st.session_state:
    st.session_state["show_admin"] = False

# ---------- Login / Logout ----------
def login(username, password):
    hashed = hash_password(password)

    if username == ADMIN_USERNAME and hashed == ADMIN_PASSWORD_HASH:
        st.session_state['logged_in'] = True
        st.session_state['username'] = username
        st.session_state['is_admin'] = True
        return True

    if username in CREDENTIALS and CREDENTIALS[username] == hashed:
        st.session_state['logged_in'] = True
        st.session_state['username'] = username
        st.session_state['is_admin'] = False
        return True

    return False

def logout():
    st.session_state['logged_in'] = False
    st.session_state['username'] = ""
    st.session_state['is_admin'] = False
    st.session_state["show_admin"] = False
    st.rerun()

def register_user(username, password):
    if not username:
        return False, "Please provide a username."

    current_users = load_users()

    if username in current_users:
        return False, "Username already exists!"
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Za-z]", password):
        return False, "Password must contain at least one alphabet."

        # Check for at least one digit
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number."

        # Check for at least one special character
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character."
    current_users[username] = hash_password(password)
    save_users(current_users)

    global CREDENTIALS
    CREDENTIALS = current_users

    return True, "Registration successful! You can now log in."

# ---------- Load movie data ----------
movies_dict = pickle.load(open('movie_dict.pkl', 'rb'))
movies = pd.DataFrame(movies_dict)
similarity = pickle.load(open('similarity.pkl', 'rb'))

# ---------- OMDb poster fetch ----------
def fetch_poster(movie_name):
    api_key = "e4a33787"
    try:
        url = f"http://www.omdbapi.com/?t={movie_name}&apikey={api_key}"
        response = requests.get(url, timeout=5)
        data = response.json()
        poster_url = data.get('Poster', "")
        if poster_url == "N/A" or not poster_url:
            poster_url = "https://via.placeholder.com/300x450?text=No+Image+Available"
        return poster_url
    except Exception:
        return "https://via.placeholder.com/300x450?text=No+Image+Available"

# ---------- Recommendation logic ----------
def recommend(movie):
    movie_index = movies[movies['title'] == movie].index[0]
    distances = similarity[movie_index]
    movie_list = sorted(list(enumerate(distances)), reverse=True, key=lambda x: x[1])[1:6]

    recommended_movies = []
    recommended_posters = []
    for i in movie_list:
        movie_name = movies.iloc[i[0]].title
        recommended_movies.append(movie_name)
        recommended_posters.append(fetch_poster(movie_name))
    return recommended_movies, recommended_posters

# ---------- ADMIN DASHBOARD ----------
def admin_dashboard():
    st.title("⚙️ Admin Dashboard")

    # Manage Users
    st.subheader("🧑‍💼 Manage Users")
    users = load_users()
    user_list = [u for u in users.keys() if u != ADMIN_USERNAME]

    if user_list:
        selected_user = st.selectbox("Select a user to delete:", user_list)
        if st.button("Delete Selected User"):
            del users[selected_user]
            save_users(users)
            st.success(f"User '{selected_user}' deleted successfully!")
            st.rerun()
    else:
        st.info("No users available.")

    st.markdown("---")

    # Manage Comments
    st.subheader("💬 Manage Comments")
    comments = st.session_state.comments

    if comments:
        for idx, c in enumerate(comments):
            st.markdown(f"**{c['user']}** 🕒 {c['time']}  \n> {c['text']}")
            if st.button(f"Delete Comment #{idx}", key=f"delc_{idx}"):
                comments.pop(idx)
                save_comments_to_file(comments)
                st.success("Comment deleted.")
                st.rerun()
    else:
        st.info("No comments found.")

    st.markdown("---")
    if st.button("⬅️ Back to Main App"):
        st.session_state["show_admin"] = False
        st.rerun()


#  MAIN APP


if st.session_state["show_admin"]:
    admin_dashboard()
    st.stop()

if not st.session_state['logged_in']:
    st.title("🔐 Movie Recommender — Login / Register")

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        st.subheader("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if login(username, password):
                st.success(f"Welcome, {username}!")
                st.rerun()
            else:
                st.error("Invalid username or password!")

    with tab2:
        st.subheader("Create a new account")
        new_user = st.text_input("Choose a Username")
        new_pass = st.text_input("Choose a Password", type="password")
        if st.button("Register"):
            success, msg = register_user(new_user, new_pass)
            if success:
                st.success(msg)
            else:
                st.error(msg)

else:
    st.sidebar.write(f"👋 Logged in as **{st.session_state['username']}**")

    if st.sidebar.button("Logout"):
        logout()

    if st.session_state['is_admin']:
        if st.sidebar.button("⚙️ Admin Dashboard"):
            st.session_state["show_admin"] = True
            st.rerun()

    st.title("🎬 Movie Recommender System")
    st.subheader("Choose a movie and click Recommend to get similar ones 🍿")

    selected_movie_name = st.selectbox('Select a movie:', movies['title'].values)

    if st.button('Recommend'):
        recommended_movies, recommended_posters = recommend(selected_movie_name)
        st.session_state['last_recommendations'] = {
            "movies": recommended_movies,
            "posters": recommended_posters
        }

    if st.session_state['last_recommendations']["movies"]:
        st.subheader('Top Recommendations:')
        cols = st.columns(5)
        for idx, col in enumerate(cols):
            with col:
                st.text(st.session_state['last_recommendations']["movies"][idx])
                st.image(st.session_state['last_recommendations']["posters"][idx])

    st.markdown("---")
    st.subheader("💬 Comments")

    if "comment_box" not in st.session_state:
        st.session_state.comment_box = ""

    def post_comment():
        new_comment = st.session_state.comment_box.strip()
        if new_comment:
            comment_entry = {
                "user": st.session_state["username"],
                "text": new_comment,
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            st.session_state.comments.append(comment_entry)
            save_comments_to_file(st.session_state.comments)
            st.session_state.comment_box = ""
            st.success("Comment posted!")
        else:
            st.warning("Write something before posting.")

    st.text_area("Share your thoughts:", key="comment_box", height=100)
    st.button("Post Comment", on_click=post_comment)

    comments = st.session_state.comments
    if comments:
        st.write("### 🗨️ All Comments:")
        for c in reversed(comments):
            st.markdown(f"**{c['user']}** 🕒 {c['time']}  \n> {c['text']}")
    else:
        st.info("No comments yet.")

