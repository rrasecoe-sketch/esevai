from flask import Flask, render_template, request, redirect, session, send_file, flash
import sqlite3
from datetime import datetime
import pandas as pd

app = Flask(__name__)
app.secret_key = "esevai_secret"

DB = "esevai.db"


def db():
    return sqlite3.connect(DB)


def init_db():

    conn = db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS customers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        mobile TEXT,
        aadhaar TEXT,
        service TEXT,
        govt_fee REAL,
        service_fee REAL,
        total_fee REAL,
        date TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    c.execute("INSERT OR IGNORE INTO users VALUES (1,'admin','admin123','admin')")
    c.execute("INSERT OR IGNORE INTO users VALUES (2,'user','user123','user')")

    conn.commit()
    conn.close()


# LOGIN
@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        conn = db()
        c = conn.cursor()

        c.execute("SELECT role FROM users WHERE username=? AND password=?",(username,password))
        user = c.fetchone()

        conn.close()

        if user:

            session["role"] = user[0]

            if user[0] == "admin":
                return redirect("/")
            else:
                return redirect("/add")

        else:
            flash("Invalid Login")

    return render_template("login.html")


# LOGOUT
@app.route("/logout")
def logout():

    session.clear()
    return redirect("/login")


# DASHBOARD
@app.route("/")
def dashboard():

    if session.get("role") != "admin":
        return redirect("/add")

    conn = db()
    df = pd.read_sql_query("SELECT * FROM customers", conn)
    conn.close()

    today = datetime.now().strftime("%Y-%m-%d")
    month = datetime.now().strftime("%Y-%m")
    year = datetime.now().strftime("%Y")

    if df.empty:

        data = {
            "today_service":0,
            "month_service":0,
            "year_service":0,
            "today_govt":0,
            "month_govt":0,
            "year_govt":0
        }

    else:

        df["date"] = pd.to_datetime(df["date"])

        data = {

        "today_service": df[df["date"].dt.strftime("%Y-%m-%d")==today]["service_fee"].sum(),

        "month_service": df[df["date"].dt.strftime("%Y-%m")==month]["service_fee"].sum(),

        "year_service": df[df["date"].dt.strftime("%Y")==year]["service_fee"].sum(),

        "today_govt": df[df["date"].dt.strftime("%Y-%m-%d")==today]["govt_fee"].sum(),

        "month_govt": df[df["date"].dt.strftime("%Y-%m")==month]["govt_fee"].sum(),

        "year_govt": df[df["date"].dt.strftime("%Y")==year]["govt_fee"].sum()
        }

    return render_template("dashboard.html",data=data)


# ADD SERVICE
@app.route("/add",methods=["GET","POST"])
def add():

    if request.method=="POST":

        govt=float(request.form["govt_fee"])
        service=float(request.form["service_fee"])
        total=govt+service

        service_name=request.form["service"]

        if service_name=="Other":
            service_name=request.form["other_service"]

        conn=db()
        c=conn.cursor()

        c.execute("""
        INSERT INTO customers
        (name,mobile,aadhaar,service,govt_fee,service_fee,total_fee,date)
        VALUES (?,?,?,?,?,?,?,?)
        """,(

        request.form["name"],
        request.form["mobile"],
        request.form["aadhaar"],
        service_name,
        govt,
        service,
        total,
        datetime.now().strftime("%Y-%m-%d")

        ))

        conn.commit()
        conn.close()

        flash("Service Added Successfully")

        return redirect("/report")

    return render_template("add_service.html")


# REPORT WITH DATE RANGE
@app.route("/report",methods=["GET","POST"])
def report():

    if session.get("role")!="admin":
        return redirect("/add")

    conn=db()

    query="SELECT * FROM customers"
    params=()

    start_date=request.form.get("start_date")
    end_date=request.form.get("end_date")

    if start_date and end_date:

        query+=" WHERE date BETWEEN ? AND ?"
        params=(start_date,end_date)

    query+=" ORDER BY date DESC"

    df=pd.read_sql_query(query,conn,params=params)
    conn.close()

    total_service=df["service_fee"].sum() if not df.empty else 0
    total_govt=df["govt_fee"].sum() if not df.empty else 0

    df["Actions"]=df["id"].apply(lambda x:
        f'<a href="/edit/{x}" class="btn btn-warning btn-sm">Edit</a> '
        f'<a href="/delete/{x}" class="btn btn-danger btn-sm">Delete</a>'
    )

    table=df.to_html(classes="table table-striped",index=False,escape=False)

    return render_template("report.html",
                           table=table,
                           total_service=total_service,
                           total_govt=total_govt)


# EDIT
@app.route("/edit/<int:id>",methods=["GET","POST"])
def edit(id):

    conn=db()
    c=conn.cursor()

    if request.method=="POST":

        govt=float(request.form["govt_fee"])
        service=float(request.form["service_fee"])
        total=govt+service

        c.execute("""
        UPDATE customers SET
        name=?,mobile=?,aadhaar=?,service=?,govt_fee=?,service_fee=?,total_fee=?
        WHERE id=?
        """,(

        request.form["name"],
        request.form["mobile"],
        request.form["aadhaar"],
        request.form["service"],
        govt,
        service,
        total,
        id
        ))

        conn.commit()
        conn.close()

        return redirect("/report")

    c.execute("SELECT * FROM customers WHERE id=?",(id,))
    customer=c.fetchone()

    conn.close()

    return render_template("edit.html",customer=customer)


# DELETE
@app.route("/delete/<int:id>")
def delete(id):

    conn=db()
    c=conn.cursor()

    c.execute("DELETE FROM customers WHERE id=?",(id,))
    conn.commit()
    conn.close()

    return redirect("/report")


# EXPORT EXCEL
@app.route("/export")
def export():

    conn=db()
    df=pd.read_sql_query("SELECT * FROM customers",conn)
    conn.close()

    file="esevai_report.xlsx"

    df.to_excel(file,index=False)

    return send_file(file,as_attachment=True)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)