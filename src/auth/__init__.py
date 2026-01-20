"""Authentication module for user accounts"""
from flask_login import LoginManager

login_manager = LoginManager()
login_manager.login_view = 'index'
login_manager.login_message = 'Please log in to access this page.'

