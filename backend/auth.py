from sqlite3 import IntegrityError

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .models import User


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """Create a new user account and start an authenticated session."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not name or not email or not password or not confirm_password:
            flash("All fields are required.", "error")
        elif password != confirm_password:
            flash("Passwords do not match.", "error")
        elif User.get_by_email(email):
            flash("An account with that email already exists.", "error")
        else:
            try:
                user = User.create(name=name, email=email, password=password)
                login_user(user)
                flash("Welcome aboard. Your account is ready.", "success")
                return redirect(url_for("dashboard"))
            except IntegrityError:
                flash("That email is already registered.", "error")

    return render_template("signup.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate an existing user."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        user = User.get_by_email(email)

        if not user or not user.verify_password(password):
            flash("Invalid email or password.", "error")
        else:
            login_user(user)
            flash("Logged in successfully.", "success")
            return redirect(url_for("dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    """End the current user session."""
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("landing"))
