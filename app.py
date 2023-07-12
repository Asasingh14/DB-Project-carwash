import decimal

from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
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

@app.context_processor
def inject_user():
    if 'user' in session:
        return {'user': session['user']}
    return {'user': None}


@app.route('/logout')
def logout():
    # remove the username from the session if it's there
    session.pop('user', None)
    return redirect(url_for('home'))


@app.route('/admin')
def admin():
    # Check if user is logged in and if the role is 'Employee'
    if 'user' in session and session['user']['role'] == 'Employee':
        return render_template('admin.html')
    else:
        return redirect(url_for('login'))  # or you might want to return 403 forbidden error
    return render_template('admin.html')


@app.route('/manage-users/')
def manage_users():
    if 'user' in session and session['user']['role'] == 'Customer':
        flash('Please sign in first', 'danger')
        return redirect('/login')
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
        print(len(email))
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
            args = [first_name, last_name, email, hashed_password, phone]

            if role == 'Customer':
                cur.callproc('InsertUserAndCustomer', args)
            elif role == 'Employee':
                position = request.form.get('position')
                salary = decimal.Decimal(request.form.get('salary'))
                print(type(salary))
                args += [position, salary]
                print(args)

                cur.callproc('insert_user_employee', args)

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
        email = request.form['email']
        role = request.form['role']
        first_name = request.form['first_name']
        last_name = request.form['last_name']

        if role == 'Customer':
                print(first_name, last_name, email)
                cur.execute(
                    f"UPDATE User SET email = '{email}',first_name = '{first_name}', last_name = '{last_name}' , customer_id = {id} WHERE customer_id = {id}")
                cur.execute(f"UPDATE Customer SET first_name = '{first_name}', last_name = '{last_name}' WHERE customer_id = {id}")
        elif role == 'Employee':
            cur.execute(f"UPDATE User SET email = '{email}', employee_id = {id} WHERE employee_id = {id}")
            if 'position' in request.form and 'team_id' in request.form and 'salary' in request.form and 'contact_no' in request.form:

                position = request.form['position']
                team_id = request.form['team_id']
                salary = request.form['salary']
                contact_no = request.form['contact_no']
                cur.execute(
                    f"UPDATE User SET email = '{email}',first_name = '{first_name}', last_name = '{last_name}', employee_id = {id} WHERE customer_id = {id}")
                cur.execute(f"UPDATE Employee SET position = '{position}', team_id = {team_id}, salary = {salary}, contact_no = '{contact_no}' WHERE employee_id = {id}")

        mysql.connection.commit()
        flash('User updated', 'success')
        return redirect('/manage-users')
    else:
        cur = mysql.connection.cursor()
        result_value = cur.execute(f"SELECT * FROM User WHERE customer_id = {id} OR employee_id = {id}")

        if result_value > 0:
            user = cur.fetchone()
            user_form = {}
            user_form['first_name'] = user['first_name']
            user_form['last_name'] = user['last_name']
            user_form['email'] = user['email']
            user_form['role'] = user['role']

            if user['role'] == 'Employee':
                cur.execute(f"SELECT * FROM Employee WHERE employee_id = {id}")
                employee = cur.fetchone()
                user_form['position'] = employee['position']
                user_form['team_id'] = employee['team_id']
                user_form['salary'] = employee['salary']
                user_form['contact_no'] = employee['contact_no']

            return render_template('edit-user.html', user_form=user_form)
        else:
            flash('User not found', 'error')
            return redirect('/manage-users')


@app.route('/delete-user/<int:id>/')
def delete_user(id):
    cur = mysql.connection.cursor()
    cur.execute(f"DELETE FROM User WHERE user_id = {id}")
    mysql.connection.commit()
    flash("The user is deleted", "success")
    return redirect('/manage-users')

@app.route('/supplies', methods=['GET', 'POST'])
def manage_supplies():
    if request.method == 'POST':
        details = request.form
        name = details['name']
        supplier_id = details['supplier_id']
        used_for = details['used_for']
        price = details['price']
        quantity = details['quantity']
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO Supplies(name, supplier_id, used_for, price, quantity) VALUES (%s, %s, %s, %s, %s)", (name, supplier_id, used_for, price, quantity))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('manage_supplies'))

    cur = mysql.connection.cursor()
    result_value = cur.execute("SELECT Supplies.name, Supplies.price, Supplies.quantity, Supplier.company, Supplier.supplier_id FROM Supplies INNER JOIN Supplier ON Supplies.supplier_id = Supplier.supplier_id")
    if result_value > 0:
        suppliers_details = cur.fetchall()
        print(suppliers_details)
        return render_template('manage-supplies.html', suppliers_details=suppliers_details)
    return render_template('manage-supplies.html', suppliers_details=None)

@app.route('/delete_supplier/<int:id>', methods=['POST', 'GET'])
def delete_supplier(id):
    flash("Record Has Been Deleted Successfully")
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM Supplier WHERE supplier_id=%s", (id,))
    mysql.connection.commit()
    return redirect(url_for('manage_supplies'))

@app.route('/order_supplies/<int:id>', methods=['POST', 'GET'])
def order_supplies(id):
    if request.method == 'POST':
        quantity = request.form['quantity']
        cur = mysql.connection.cursor()
        cur.execute("UPDATE Supplies SET quantity=quantity+%s WHERE supplies_id=%s", (quantity, id))
        mysql.connection.commit()
        flash("Data Updated Successfully")
        return redirect(url_for('manage_supplies'))
    return render_template('order_supplies.html', id=id)

@app.route('/manage_bookings')
def manage_bookings():
    # Check if user is logged in and if the role is 'Employee'
    if 'user' not in session or session['user']['role'] != 'Employee':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))

    # Initialize cursor
    cur = mysql.connection.cursor()

    try:
        # # Execute the query
        # cur.execute("SELECT * FROM bookings")

        cur.execute("""
            SELECT Booking.booking_id, Booking.time, Booking.status, Customer.first_name, Package.type 
            FROM Booking 
            INNER JOIN Customer ON Booking.customer_id = Customer.customer_id 
            INNER JOIN Package ON Booking.package_id = Package.package_id
        """)

        # Fetch all rows
        bookings = cur.fetchall()

        # If no bookings found, show a message
        if not bookings:
            flash("No bookings found", "info")
            return render_template('manage-bookings.html', bookings=None)

        return render_template('manage-bookings.html', bookings=bookings)

    except Exception as e:
        # An error occurred while fetching data from the database
        print(f"An error occurred: {e}")
        flash("An error occurred while fetching bookings.", "danger")
        return render_template('manage-bookings.html', bookings=None)

    finally:
        # Close the cursor
        cur.close()

@app.route('/update-booking/<int:id>/', methods=['GET', 'POST'])
def update_booking(id):
    # Check if user is logged in and if the role is 'Employee'
    if 'user' not in session or session['user']['role'] != 'Employee':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    try:
        if request.method == 'POST':
            # Collect form data here
            # Assuming the form contains fields 'date', 'time', 'status'
            date = request.form.get('date')
            time = request.form.get('time')
            status = request.form.get('status')

            # Update the booking in the database
            cur.execute(
                f"UPDATE bookings SET date = '{date}', time = '{time}', status = '{status}' WHERE booking_id = {id}")
            mysql.connection.commit()

            flash('Booking updated successfully!', 'success')
            return redirect(url_for('manage_bookings'))
        else:
            # In the case of GET, we retrieve the booking info and display it in the form
            cur.execute(f"SELECT * FROM bookings WHERE booking_id = {id}")
            booking = cur.fetchone()

            if not booking:
                flash('No booking found with this ID', 'danger')
                return redirect(url_for('manage_bookings'))

            return render_template('edit-booking.html', booking=booking)

    except Exception as e:
        # An error occurred while updating the booking
        print(f"An error occurred: {e}")
        flash("An error occurred while updating the booking.", "danger")
        return redirect(url_for('manage_bookings'))

    finally:
        # Close the cursor
        cur.close()


@app.route('/bookings/verify', methods=['POST'])
def verify_booking():
    booking_id = request.form.get('booking_id')
    employee_id = session.get('employee_id')  # Assuming you stored logged-in employee's id in the session
    cur = mysql.connection.cursor()
    cur.execute("UPDATE bookings SET verified_by=%s WHERE booking_id=%s", (employee_id, booking_id))
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('manage_bookings'))


@app.route('/delete-booking/<int:id>/')
def delete_booking(id):
    # Check if user is logged in and if the role is 'Employee'
    if 'user' not in session or session['user']['role'] != 'Employee':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    try:
        # Execute delete query
        cur.execute(f"DELETE FROM bookings WHERE booking_id = {id}")
        mysql.connection.commit()

        flash('Booking deleted successfully!', 'success')

    except Exception as e:
        # An error occurred while deleting the booking
        print(f"An error occurred: {e}")
        flash("An error occurred while deleting the booking.", "danger")

    finally:
        # Close the cursor
        cur.close()

    return redirect(url_for('manage_bookings'))


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


@app.route('/membership', methods=['GET', 'POST'])
def handle_membership():
    cur = mysql.connection.cursor()
    if 'user' in session:  # User is logged inr
        if request.method == 'POST':
            # Extract data from request
            tier = request.form.get('membership_tier')
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')

            # Create a new Membership record
            cur.execute("INSERT INTO Membership (username, tier, start_date, end_date) VALUES (%s, %s, %s, %s)",
                        (session['user'], tier, start_date, end_date,))
            mysql.connection.commit()

            return redirect(url_for('handle_membership'))  # Redirect to GET request handler

        else:
            # Fetch user's membership details
            result = cur.execute("""
                SELECT User.email, Customer.member_id, Membership.*
                FROM User
                INNER JOIN Customer ON User.customer_id = Customer.customer_id
                INNER JOIN Membership ON Customer.member_id = Membership.member_id
                WHERE User.email = %s
            """, (session['user'],))

            if result > 0:  # User is a member
                membership = cur.fetchone()
                return render_template('membership.html', is_member=True, data=membership)

            else:  # User is not a member
                cur.execute("SELECT * FROM Membership_Tier")
                memberships = cur.fetchall()
                print(memberships)
                return render_template('membership.html', is_member=False, available_memberships=memberships)

    else:  # User is not logged in
        cur.execute("SELECT * FROM Membership_Tier")
        memberships = cur.fetchall()
        print(memberships)
        return render_template('membership.html', is_member=False, available_memberships=memberships, login_required=True)




if __name__ == '__main__':
    app.run(debug=True)
