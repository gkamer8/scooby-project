from flask import Flask, render_template, request, g, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import time

app = Flask(__name__)

app.secret_key = 'potato yeet'

DATABASE = 'awesome.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route("/")
def index():
    if 'loggedin' in session and session['loggedin']:
        return render_template('home.html', loggedin=True, username=session['username'])
    return render_template('home.html', loggedin=False)

@app.route('/login', methods =['GET', 'POST'])
def login():
    is_register = True if 'register' in request.form else False

    required_reg_fields = ['register', 'username', 'password', 'email']
    has_everything_for_reg = 0==sum([x not in request.form for x in required_reg_fields])

    required_login_fields = ['username', 'password']
    has_everything_for_login = 0==sum([x not in request.form for x in required_login_fields])

    if request.method == 'POST' and not is_register and has_everything_for_login:
        username = request.form['username']
        password = request.form['password']

        cursor = get_db().cursor()
        
        cursor.execute('SELECT username, id, password_hash, top_admin FROM users WHERE username = ?', (username,))
        account = cursor.fetchone()

        if account and check_password_hash(account[2], password):
            session['loggedin'] = True
            session['id'] = account[1]
            session['username'] = account[0]
            session['top_admin'] = account[3]
            return redirect('/')
        else:
            return 'Incorrect username / password !'
    elif request.method == 'POST' and is_register and has_everything_for_reg:
        username = request.form['username']

        password = request.form['password']
        password = generate_password_hash(password)

        email = request.form['email']

        if 'harvard.edu' not in email:
            return "You need a harvard email."

        db = get_db()
        cursor = db.cursor()
        
        sql = """
            INSERT INTO users (username, password_hash, email)
            VALUES(?, ?, ?);
        """

        cursor.execute(sql, (username, password, email))
        db.commit()

        print("here")
        
        # Now login
        cursor.execute('SELECT username, id, password_hash FROM users WHERE username = ? AND password_hash = ?', (username, password))
        account = cursor.fetchone()

        if account:
            session['loggedin'] = True
            session['id'] = account[1]
            session['username'] = account[0]
            session['top_admin'] = False
            return redirect('/')
        else:
            return 'Incorrect username / password !'
    else:
        return render_template('login.html')
    

@app.route('/post', methods=['GET', 'POST'])
def post():

    if not session['loggedin']:
        return redirect('/')
    
    if request.method == 'POST':

        required_fields = ['title', 'text', 'reply_to']
        has_everything_for_post = 0==sum([x not in request.form for x in required_fields])

        if has_everything_for_post:
            db = get_db()
            cursor = db.cursor()
            
            sql = """
                INSERT INTO posts (userid, title, text, unix_time, reply_to)
                VALUES(?, ?, ?, ?, ?);
            """
            unix_time = int(time.time())

            if request.form['reply_to'] == -1:
                reply_to=None
            else:
                try:
                    reply_to=int(request.form['reply_to'])
                except ValueError:
                    reply_to = -1

            cursor.execute(sql, (session['id'], request.form['title'], request.form['text'], unix_time, reply_to))
            db.commit()
    
    db = get_db()
    cursor = db.cursor()
    
    if session['top_admin']:
        sql = """

            SELECT  originals.title,
                    originals.text,
                    originals.postid,
                    originals.unix_time,
                    replies.title as ReplyTitle,
                    replies.text as ReplyText,
                    replies.unix_time as ReplyTime
            FROM
                (SELECT title, text, postid, unix_time
                FROM posts
                WHERE reply_to = -1
                ORDER BY unix_time DESC) originals
            LEFT JOIN
                (SELECT title, text, reply_to, unix_time
                FROM posts
                WHERE reply_to != -1
                ORDER BY unix_time DESC) replies
            ON replies.reply_to=originals.postid
        """
        cursor.execute(sql)
        posts = cursor.fetchall()
    else:
        sql = """

            SELECT  originals.title,
                    originals.text,
                    originals.postid,
                    originals.unix_time,
                    replies.title as ReplyTitle,
                    replies.text as ReplyText,
                    replies.unix_time as ReplyTime
            FROM
                (SELECT title, text, postid, unix_time
                FROM posts
                WHERE userid=?
                AND reply_to = -1) originals
            LEFT JOIN
                (SELECT title, text, reply_to, unix_time
                FROM posts
                WHERE userid=?
                AND reply_to != -1) replies
            ON replies.reply_to=originals.postid
            ORDER BY originals.unix_time DESC, ReplyTime ASC
        """
        cursor.execute(sql, (session['id'],session['id']))
        posts = cursor.fetchall()

    my = {
        'title': 0,
        'text': 1,
        'post_id': 2,
        'unix_time': 3,
        'reply_title': 4,
        'reply_text': 5,
        'reply_unix_time': 6
    }

    post_dict = dict()
    for orig in posts:
        if orig[my['reply_title']] is not None:
            to_add = (orig[my['reply_title']], orig[my['reply_text']], orig[my['reply_unix_time']], orig[my['post_id']])

        if orig[my['post_id']] in post_dict and orig[my['reply_title']] is not None:  # post id
            post_dict[orig[my['post_id']]][4].append(to_add)  # reply title, text, time
        
        elif orig[my['post_id']] not in post_dict and orig[my['reply_title']] is None:
            post_dict[orig[my['post_id']]] = (orig[0], orig[1], orig[2], orig[3], [])  # title, text, id, time
        
        elif orig[2] not in post_dict and orig[4] is not None:
            post_dict[orig[2]] = (orig[0], orig[1], orig[2], orig[3], [to_add])  # title, text, id, time

    post_list = [post_dict[k] for k in post_dict]  # would need to sort, etc.

    kwargs = {
        'posts': post_list,
        'top_admin': session['top_admin'],
        'loggedin': session['loggedin'],
        'username': session['username'] 
    }
    return render_template('posts.html', **kwargs)

@app.route('/logout')
def clear():
    session.clear()
    return redirect('/')