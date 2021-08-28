from __future__ import print_function
import os
from flask import Flask, render_template, request, redirect, flash, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import *
from dateutil.relativedelta import relativedelta

from models.models import User, Contact
from models.database import db_session
from app.key import SECRET_KEY, SENDER_GMAIL

from apscheduler.schedulers.background import BackgroundScheduler
from app.mail import create_message, send_message
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from sqlalchemy.sql import text

scheduler = BackgroundScheduler()
SCOPES = ['https://www.googleapis.com/auth/gmail.send']
def send_gmail():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'app/secret_cred.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('gmail', 'v1', credentials=creds)

    today = date.today()

    _two_weeks_ago = today - relativedelta(weeks=2)
    two_weeks_ago = _two_weeks_ago.strftime('%Y-%m-%d') #datetime型から文字列に変換
    _one_month_ago = today - relativedelta(months=1)
    one_month_ago = _one_month_ago.strftime('%Y-%m-%d') #datetime型から文字列に変換

    _two_weeks_later = today + relativedelta(weeks=2)
    two_weeks_later = _two_weeks_later.strftime('%Y-%m-%d') #datetime型から文字列に変換
    _one_month_later = today + relativedelta(months=1)
    one_month_later = _one_month_later.strftime('%Y-%m-%d') #datetime型から文字列に変換

    email_list = []
    select_week = text(
        "SELECT * FROM users JOIN contacts ON users.id = contacts.user_id WHERE started_at = '{}' AND is_2week = 1 AND is_1month = 0"
        .format(two_weeks_ago))
    select_month = text(
        "SELECT * FROM users JOIN contacts ON users.id = contacts.user_id WHERE started_at = '{}' AND is_2week = 0 AND is_1month = 1"
        .format(one_month_ago))

    # email_listに今日が交換日であるユーザーのemailを追加
    for user in db_session.execute(select_week):
        email_list.append(user["email"])
    for user in db_session.execute(select_month):
        email_list.append(user["email"])

    update_week = text(
        "UPDATE contacts SET started_at = '{}' WHERE started_at = '{}' AND is_2week = 1 AND is_1month = 0"
        .format(two_weeks_later, two_weeks_ago)
    )
    update_month = text(
        "UPDATE contacts SET started_at = '{}' WHERE started_at = '{}' AND is_2week = 0 AND is_1month = 1"
        .format(one_month_later, one_month_ago)
    )

    # 今日が交換日であるユーザーのstarted_atを更新
    db_session.execute(update_week)
    db_session.execute(update_month)
    db_session.commit()


    sender = SENDER_GMAIL
    subject = '本日はコンタクトの交換日です'
    message_text = '本日はコンタクトの交換日です。\n今日も1日お疲れ様でした。\n登録削除はこちらから↓\nhttps://safe-eyes.jp/delete'

    # 今日が交換日のユーザーにメールを送信
    for to in email_list:
        message = create_message(sender, to, subject, message_text)
        send_message(service, 'me', message)

scheduler.add_job(send_gmail, 'cron', hour=9, minute=0, second=0)
scheduler.start()


application = Flask(__name__)
application.config["SECRET_KEY"] = SECRET_KEY
application.permanent_session_lifetime = timedelta(minutes=10)
application.config["TEMPLATES_AUTO_RELOAD"] = True

# root
@application.route("/")
def index():
    return render_template("index.html")


# ユーザー登録
@application.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        error = None
        user = User.query.filter_by(email=email).first()

        if not name:
            error = "ユーザー名を入力してください"
        elif not email:
            error = "メールアドレスを入力してください。"
        elif not password:
            error = "パスワードを入力してください。"
        elif password != confirmation:
            error = "パスワードが一致していません。"
        elif user is not None:
            error = "{}はすでに使用されています。".format(email)

        if not error:
            hashed_password = generate_password_hash(password)
            user = User(name, email, hashed_password)
            db_session.add(user)
            db_session.commit()
            user = User.query.filter_by(email=email).first()
            session.clear()
            session["user_id"] = user.id
            return redirect("/contact")

        flash(error)

    return render_template("register.html")


# ログイン
@application.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        error = None
        user = User.query.filter_by(email=email).first()

        if not email:
            error = "メールアドレスを入力してください。"
        elif not password:
            error = "パスワードを入力してください。"
        elif not user:
            error = "メールアドレスが正しくありません。"
        elif not check_password_hash(user.hashed_password, password):
            error = "パスワードが正しくありません。"

        if not error:
            session.clear()
            session["user_id"] = user.id
            return redirect("/contact")

        flash(error)

    return render_template("login.html")


# コンタクト登録
@application.route("/contact", methods=("GET", "POST"))
def contact():
    if not session:
        return redirect("/login")

    if request.method == "POST":
        type = request.form.get("radio")
        _started_at = request.form.get("started_at")
        error = None
        if type == "is_2week":
            is_2week = True
            is_1month = False
        elif type == "is_1month":
            is_2week = False
            is_1month = True

        if not type:
            error = "コンタクトのタイプを選択してください。"
        elif not _started_at:
            error = "開始日時を入力してください。"

        started_at = datetime.strptime(_started_at, '%Y-%m-%d')

        if not error:
            user_id = session["user_id"]
            contact = Contact(user_id, is_2week, is_1month, started_at)
            db_session.add(contact)
            db_session.commit()
            return render_template("done.html")

        flash(error)

    return render_template("contact.html")

@application.route("/delete", methods=("GET", "POST"))
def delete():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        error = None
        user = User.query.filter_by(email=email).first()

        if not email:
            error = "メールアドレスを入力してください。"
        elif not password:
            error = "パスワードを入力してください。"
        elif not user:
            error = "メールアドレスが正しくありません。"
        elif not check_password_hash(user.hashed_password, password):
            error = "パスワードが正しくありません。"

        if not error:
            user_id = user.id
            contact = Contact.query.filter_by(user_id=user_id).first()
            db_session.delete(user)
            db_session.delete(contact)
            db_session.commit()
            flash("登録が削除されました。")
            return redirect("/")

        flash(error)

    return render_template("delete.html")


@application.route('/<path:path>')
def free_path(path):
    return redirect("/")
    

@application.route("/favicon.ico")
def favicon():
    return application.send_static_file("favicon.ico")


if __name__ == "__main__":
    application.debug = True
    application.run()
