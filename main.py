from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
import os
import glob

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("FLASK_SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)

##Soundboard
class SoundCred:
    def __init__(self, location, person, header):
        self.location = location
        self.person = person
        self.title = header


dir_path = r"static\sounds\*.mp3"
sound_list = [sound[14:] for sound in glob.glob(dir_path)]

sorted_list = []
for item in sound_list:
    name = item.split("_")[0]
    title = item.split("_")[1].split(".")[0].title()
    sound = SoundCred(location=item, person=name, header=title)
    sorted_list.append(sound)

people = []
for item in sorted_list:
    if item.person not in people:
        people.append(item.person)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='mp',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

def admin_only(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if current_user.id == 1:
            return func(*args, **kwargs)
        return abort(403)
    return wrapper

##CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    # One2Many
    posts = relationship('BlogPost', back_populates='author')
    comments = relationship('Comments', back_populates='commenter')

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    # links to the users' primary key
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    author = relationship('User', back_populates='posts')
    # when you tap into blogid.author it then allows you to access all of the User columns
    # eg, blogid.author.name will print users.name
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    # Link to Comments One2Many
    comments = relationship('Comments', back_populates='post')

class Comments(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(250), nullable=False)
    # Link to User Many2One
    commenter_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    commenter = relationship('User', back_populates='comments')
    # Link to BlogPost Many2One
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))
    post = relationship('BlogPost', back_populates='comments')



with app.app_context():
    db.create_all()


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=["GET", "POST"])
def register():
    register_form = RegisterForm()
    if register_form.validate_on_submit():
        if User.query.filter_by(email=register_form.email.data).first():
            flash("Email already in use, try logging in!")
            return redirect(url_for('login'))

        hashed_password = generate_password_hash(
            password=register_form.password.data,
            method='pbkdf2:sha256',
            salt_length=8,
        )

        new_user = User()
        new_user.name = register_form.name.data
        new_user.email = register_form.email.data
        new_user.password = hashed_password

        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect(url_for('get_all_posts'))

    return render_template("register.html", form=register_form)


@app.route('/login', methods=["GET", "POST"])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():
        user = User.query.filter_by(email=login_form.email.data).first()
        if not user:
            flash("Invalid Email")
        elif not check_password_hash(pwhash=user.password,password=login_form.password.data):
            flash("Incorrect Password")
        else:
            login_user(user)
            return redirect(url_for('get_all_posts'))
    return render_template("login.html", form=login_form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    comment_form = CommentForm()
    if comment_form.validate_on_submit():
        new_comment = Comments(
            text=comment_form.comment.data,
            post_id=post_id,
            commenter=current_user,
        )
        db.session.add(new_comment)
        db.session.commit()
        return render_template("post.html", post=requested_post, form=comment_form)
    return render_template("post.html", post=requested_post, form=comment_form)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user, ## Buggy until databade relation
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))





@app.route("/soundboard")
def soundboard():
    return render_template("soundboard-one-page.html", sounds=sorted_list, people=people)


@app.route("/soundboard/<person>")
def person_page(person):
    return render_template("insert something here.html")

# Todo: Have homepage with an icon (card) for each person
# 	With a /home/"person" page which has a list of all files

## End Soundboard


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
