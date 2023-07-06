from flask import Flask, render_template, redirect, url_for, request, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from mysql.connector.errors import IntegrityError
from datetime import datetime, timedelta
from flask_mysqldb import MySQL
import yaml
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = "Never push this line to github public repo"

cred = yaml.load(open('cred.yaml'), Loader=yaml.Loader)
app.config['MYSQL_HOST'] = cred['mysql_host']
app.config['MYSQL_USER'] = cred['mysql_user']
app.config['MYSQL_PASSWORD'] = cred['mysql_password']
app.config['MYSQL_DB'] = cred['mysql_db']
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
mysql = MySQL(app)


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Collect form data
        first_name = request.form['first_name'].capitalize()
        last_name = request.form['last_name'].capitalize()
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Hash password
        hashed_password = generate_password_hash(password, method='sha256')

        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-z]+(?:\.[a-z]+)?$"
        if not re.match(pattern, email):
            flash('Invalid email format. Please use a valid email address!', 'danger')
            return render_template('register.html', first_name=first_name, last_name=last_name, phone=phone,
                                   email_error=True)

        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return render_template('register.html', first_name=first_name, last_name=last_name, email=email,
                                   phone=phone, password_error=True)

        cur = mysql.connection.cursor()
        try:
            args = [first_name, last_name, email, phone, hashed_password, 'Customer']
            cur.callproc('InsertUserAndCustomer', args)
            mysql.connection.commit()
        except IntegrityError:
            flash('Email already exists!', 'danger')
            return render_template('register.html', first_name=first_name, last_name=last_name, phone=phone,
                                   email_error=True)
        finally:
            cur.close()

        flash("Form Submitted Successfully", 'info')
        return redirect(url_for('home'))

    return render_template('register.html')



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Collect form data
        email = request.form['email']
        password = request.form['password']

        # Validate and handle the form data here
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM User WHERE email = %s", [email])
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user['password'], password):
            # Store the user info in session for later use
            session['user'] = user
            if user['role'] == 'Employee':
                return redirect(url_for('admin'))
            else:
                return redirect(url_for('home'))
        else:
            flash('Invalid email or password', 'danger')
            return render_template('login.html', email=email)
    return render_template('login.html')



@app.route('/logout')
def logout():
    # remove the username from the session if it's there
    session.pop('user', None)
    return redirect(url_for('home'))


@app.route('/admin')
def admin():
    # Check if user is logged in and if the role is 'Employee'
    # if 'user' in session and session['user']['role'] == 'Employee':
    #     return render_template('admin.html')
    # else:
    #     return redirect(url_for('login'))  # or you might want to return 403 forbidden error
    return render_template('admin.html')


@app.route('/manage-users/')
def manage_users():
    # try:
    #     username = session['username']
    # except:
    #     flash('Please sign in first', 'danger')
    #     return redirect('/login')

    cur = mysql.connection.cursor()
    result_value = cur.execute("SELECT * FROM User")
    if result_value > 0:
        users = cur.fetchall()
        return render_template('manage-users.html', users=users)
    else:
        return render_template('manage-users.html', users=None)


@app.route('/create-user', methods=['POST', 'GET'])
def create_user():
    if request.method == 'POST':
        # Collect form data
        first_name = request.form['first_name'].capitalize()
        last_name = request.form['last_name'].capitalize()
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        role = request.form['role']

        # Hash password
        hashed_password = generate_password_hash(password, method='sha256')

        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-z]+(?:\.[a-z]+)?$"
        if not re.match(pattern, email):
            flash('Invalid email format. Please use a valid email address!', 'danger')
            return render_template('create-user.html', first_name=first_name, last_name=last_name, phone=phone,
                                   email_error=True)

        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return render_template('create-user.html', first_name=first_name, last_name=last_name, email=email,
                                   phone=phone, password_error=True)

        cur = mysql.connection.cursor()
        try:
            args = [first_name, last_name, email, phone, hashed_password, role]

            if role == 'Customer':
                cur.callproc('InsertUserAndCustomer', args)
            # TODO: Fix Employee parsing
            elif role == 'Employee':
                position = request.form.get('position')
                team_id = request.form.get('team_id')
                salary = request.form.get('salary')

                args += [position, team_id, salary]
                print(args)

                cur.callproc('InsertUserAndEmployee', args)

            while cur.nextset(): pass
            mysql.connection.commit()
        except IntegrityError as e:
            flash('A database error occurred! Please check your input.', 'danger')
            return render_template('create-user.html', first_name=first_name, last_name=last_name, phone=phone,
                                   email_error=True)
        finally:
            cur.close()

        flash('User successfully created!', 'success')
        return redirect(url_for('manage_users'))

    return render_template("create-user.html")


@app.route('/edit-user/<int:id>/', methods=['GET', 'POST'])
def edit_user(id):
    if request.method == 'POST':
        cur = mysql.connection.cursor()
        # username = request.form['username']
        email = request.form['email']
        role = request.form['role']
        # cur.execute(f"-- UPDATE users SET username= {username}', email = '{email}', role = '{role}' WHERE user_id = {id}")
        cur.execute(f"UPDATE users SET email = '{email}', role = '{role}' WHERE user_id = {id}")
        mysql.connection.commit()
        flash('User updated', 'success')
        return redirect('/manage-users')
    else:
        cur = mysql.connection.cursor()
        result_value = cur.execute(f"SELECT * FROM User WHERE user_id = {id}")
        if result_value > 0:
            user = cur.fetchone()
            user_form = {}
            # user_form['username'] = user['username']
            user_form['email'] = user['email']
            user_form['role'] = user['role']
            return render_template('edit-user.html', user_form=user_form)


@app.route('/delete-user/<int:id>/')
def delete_user(id):
    cur = mysql.connection.cursor()
    cur.execute(f"DELETE FROM User WHERE user_id = {id}")
    mysql.connection.commit()
    flash("The user is deleted", "success")
    return redirect('/manage-users')


@app.route('/manage_supplies')
def manage_supplies():
    # Retrieve supplies data from the 'supplies' table
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM Supplies")
    supplies = cur.fetchall()
    cur.close()

    return render_template('manage-supplies.html', supplies=supplies)


@app.route('/manage_bookings')
def manage_bookings():
    # Retrieve booking data from the 'bookings' table
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM bookings")
    bookings = cur.fetchall()
    cur.close()

    return render_template('manage-bookings.html', bookings=bookings)


@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if request.method == 'POST':
        # Handle form data here
        vehicle_type = request.form.get('vehicleType')
        package = request.form.get('package')
        booking_time = request.form.get('selected-time')

        print(vehicle_type, package, booking_time)
        if not all([vehicle_type, package, booking_time]):
            flash("Please make sure all fields are selected", 'error')
            return redirect(url_for('booking'))

        flash("Booking Submitted Successfully", 'info')

        # Validate, save, and do something with data
        # Redirect or render template with success or error message
        return redirect(url_for('home'))

    if request.method == "GET":
        # If it's a GET request, show the booking form
        today = datetime.now()
        next_seven_days = [today + timedelta(days=i) for i in range(6)]
        hours = ["{0:02d}:00".format(hour) for hour in range(8, 21)]  # 08:00 to 20:00

        return render_template('booking.html', dates=next_seven_days, hours=hours)

    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)
