import os

# This gets the absolute path of the directory where the file is located.
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # A secret key is required by Flask for security purposes (e.g., sessions).
    SECRET_KEY = 'ILovePotatoesVeryMuch'

    # This sets up the database location.
    # It will create a file named 'app.db' in your main project folder.
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(basedir, 'static/uploads')

    GOOGLE_CLIENT_ID = '85744415118-h8agp3ka7fd1p0c2ech067i9spbtp74e.apps.googleusercontent.com'
    GOOGLE_CLIENT_SECRET = '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'