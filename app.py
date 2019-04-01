from flask import Flask, render_template, request, session, redirect, url_for, send_file
import os
import string
import random
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time

app = Flask(__name__)
app.secret_key = "super secret key"
IMAGES_DIR = os.path.join(os.getcwd(), "images")

connection = pymysql.connect(host="localhost",
                             user="root",
                             password="",
                             db="finstagram",
                             charset="utf8mb4",
                             port=3306,
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if not "username" in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return dec

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("home"))
    return render_template("index.html")

@app.route("/home")
@login_required
def home():
    return render_template("home.html", username=session["username"])

@app.route("/upload", methods=["GET"])
@login_required
def upload():
    return render_template("upload.html")

@app.route("/images", methods=["GET"])
@login_required
def images():
    query = "SELECT * FROM photo"
    with connection.cursor() as cursor:
        cursor.execute(query)
    data = cursor.fetchall()
    return render_template("images.html", images=data)

@app.route("/image/<owner_name>/<image_name>", methods=["GET"])
def image(owner_name, image_name):
    image_location = os.path.join(IMAGES_DIR, owner_name, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg")

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")

@app.route("/loginAuth", methods=["POST"])
def loginAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()

        with connection.cursor() as cursor:
            query = "SELECT * FROM person WHERE username = %s AND password = %s"
            cursor.execute(query, (username, hashedPassword))
        data = cursor.fetchone()
        if data:
            session["username"] = username
            return redirect(url_for("home"))

        error = "Incorrect username or password."
        return render_template("login.html", error=error)

    error = "An unknown error has occurred. Please try again."
    return render_template("login.html", error=error)

@app.route("/registerAuth", methods=["POST"])
def registerAuth():
    if request.form:
        requestData = request.form
        privFlag = 1
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()
        firstName = requestData["fname"]
        lastName = requestData["lname"]
        option = request.form['options']
        bio = requestData["bio"]

        if option == "Public":
            privFlag = 0
        elif option == "Private":
            privFlag = 1

        AV_IMAGES_DIR = os.path.join(os.getcwd(), "images", username, "avatars")
    
        if request.files:   
            image_file = request.files.get("av_imageToUpload")
            image_name = image_file.filename
            if not allowed_file(image_name):
                error = "File not recognized"
                return render_template("register.html", error=error)

            filepath = os.path.join(AV_IMAGES_DIR, image_name)

            try:
                with connection.cursor() as cursor:
                    query = "INSERT INTO person (username, password, fname, lname, avatar, isPrivate, bio) VALUES (%s, %s, %s, %s, %s, %s, %s)"
                    cursor.execute(query, (username, hashedPassword, firstName, lastName, image_name, int(privFlag), bio))
            except pymysql.err.IntegrityError:
                error = "%s is already taken." % (username)
                return render_template('register.html', error=error)    
            
            if not os.path.isdir("images"):
                os.mkdir(IMAGES_DIR)
           
            os.mkdir(os.path.join(os.getcwd(), "images", username))
            os.mkdir(os.path.join(os.getcwd(), "images", username, "avatars"));

            image_file.save(filepath)

            return redirect(url_for("login"))

    error = "An error has occurred. Please try again."
    return render_template("register.html", error=error)


@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username")
    return redirect("/")

@app.route("/uploadImage", methods=["POST"])
@login_required
def upload_image():

    if request.form:
        requestData = request.form
        followersFlag = 0
        caption_value = requestData["caption_value"]
        option = request.form["options"]

        if option == "Yes":
            followersFlag = 1
        elif option == "No":
            followersFlag = 0

        if request.files:
            image_file = request.files.get("imageToUpload", "")
            image_name = image_file.filename
            filepath = os.path.join(IMAGES_DIR, session["username"], image_name)
            imagepath  = os.path.join(session["username"], image_name)
            if os.path.exists(filepath):
                image_name = os.path.splitext(image_name)[0] + "_" + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5)) + os.path.splitext(image_name)[1]
                filepath = os.path.join(IMAGES_DIR, session["username"], image_name)
                imagepath  = os.path.join(session["username"], image_name)

            if allowed_file(image_name):
                image_file.save(filepath)
                query = "INSERT INTO photo (timestamp, filePath, photoOwner, caption, allFollowers) VALUES (%s, %s, %s, %s, %s)"
                with connection.cursor() as cursor:
                    cursor.execute(query, (time.strftime('%Y-%m-%d %H:%M:%S'), imagepath, session["username"], caption_value, 66))
                    session["photoID"] = cursor.lastrowid
                message = "Image has been successfully uploaded."
                if followersFlag == 1:
                    return render_template("upload.html", message=message)
                elif followersFlag == 0:
                    return redirect("/closeFriendGroups")
            else:
                message = "Failed to upload image."
                return render_template("upload.html", message=message)

        else:
            message = "Failed to upload image."
            return render_template("upload.html", message=message)

    else:
        message = "Failed to upload image."
        return render_template("upload.html", message=message)

@app.route("/closeFriendGroups", methods=["GET"])
@login_required
def getCloseFriendGroups():
    username = session["username"]
    try:
        with connection.cursor() as cursor:
            query = "SELECT groupName, groupOwner FROM Belong left join (SELECT * FROM Share where photoID=%s) AS T2 using (groupName, groupOwner) WHERE photoID is NULL AND username = %s"
            cursor.execute(query, (session["photoID"], username))
    except pymysql.err.IntegrityError:
        error = "An error has occured"
        return render_template("closeFriendGroups.html", message=error, hider="display:none;")  
    if cursor.rowcount == 0:
        error = "%s has no more Close Friend Groups to share photo with." % (username)
        return render_template("closeFriendGroups.html", message=error, hider="display:none;")  

    else:
        values = []
        groupOwners = []
        groupNames = []
        data = cursor.fetchall()
        i = 0
        for line in data:
            values.append(str(i) + " - GroupName: " + str(line["groupName"]) + " | " + "GroupOwner: " + str(line["groupOwner"]))
            groupOwners.append(str(line["groupOwner"]))
            groupNames.append(str(line["groupName"]))
            i = i + 1
        session["GroupNames"] = groupNames
        session["GroupOwners"] = groupOwners
        session["GroupValues"] = values
        return render_template("closeFriendGroups.html", groupsData=values)

@app.route("/select_closeFriendsGroup", methods=["GET", "POST"])
@login_required
def select_closeFriendGroups():
    if request.form:
        option_data = int(request.form["options"])
        if option_data < len(session["GroupOwners"]):
            groupOwner =  (session["GroupOwners"])[option_data]
            groupName =  (session["GroupNames"])[option_data]
            print session["photoID"]
            print groupName
            print groupOwner
            if request.form:
                try:
                    with connection.cursor() as cursor:
                        query = "INSERT INTO share (groupName, groupOwner, photoID) VALUES (%s, %s, %s)"
                        cursor.execute(query, (groupName, groupOwner, int(session["photoID"])))
                except pymysql.err.IntegrityError:
                    error = "You've already selected this group"
                    return redirect("/closeFriendGroups") 
                try:
                    session.pop("GroupNames") 
                    session.pop("GroupOwners")  
                    session.pop("GroupOwners") 
                except:
                    pass
                return redirect("/closeFriendGroups")
            error = "An error has occured"
            return render_templaterender_template("closeFriendGroups.html", message=error, hider="display:none;")  
        else:
            error = "An error has occured"
            return render_template("closeFriendGroups.html", message=error, hider="display:none;")  
    else:
        error = "An error has occured"
        return render_template("closeFriendGroups.html", message=error, hider="display:none;")   

@app.route("/follow", methods=["GET"])
@login_required
def follow():
    username = session["username"]
    try:
        with connection.cursor() as cursor:
            query = "SELECT * FROM Follow where followerUsername = %s AND acceptedFollow = 0"
            cursor.execute(query, (username))
    except pymysql.err.IntegrityError:
        error = "An error has occured"
        return render_template('follow.html', error=error, hider="display:none;")   
    if cursor.rowcount == 0:
        error = "No follow requests."
        return render_template('follow.html', error=error, hider="display:none;")  
    else:
        values = []
        followeeUsernames = []
        data = cursor.fetchall()
        i = 0
        for line in data:
            followeeUsernames.append(str(i) + " - " + str(line["followeeUsername"]))
            values.append(str(line["followeeUsername"]))
            i = i + 1
        session["followValues"] = values
        session["followeeUsernames"] = followeeUsernames
        return render_template("follow.html", followData=followeeUsernames, error="Follow requests to accept")

@app.route("/followAuth", methods=["POST"])
@login_required
def followAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO follow (followerUsername, followeeUsername, acceptedFollow) VALUES (%s, %s, 0)"
                cursor.execute(query, (username, session["username"]))
        except pymysql.err.IntegrityError:
            error = "You are already following %s or %s doesn't exist ." % (username, username)
            return render_template('follow.html', error=error)    
        error = "Sucess"
        return redirect("/follow")  
                  
    error = "An error has occurred. Please try again."
    return render_template('follow.html', error=error, hider="display:none;") 

@app.route("/acceptFollows", methods=["POST"])
@login_required
def acceptfollowAuth():
    flag = 1
    if request.form:
        option_data =  request.form["options"]
        if not option_data.isdigit():
            option_data =  (request.form["options"]).split('-', 1)[0]
            if int(option_data) >= len(session["followValues"]) or not option_data.isdigit():
                error = "An error has occurred. Please try again."
                return render_template('follow.html', error=error, hider="display:none;") 
            deleteUsername =  (session["followValues"])[int(option_data)]
            flag = 0
        else: 
            if int(option_data) >= len(session["followValues"]):
                error = "An error has occurred. Please try again."
                return render_template('follow.html', error=error, hider="display:none;") 
            followeeUsername = (session["followValues"])[int(option_data)]
        if flag:
            try:
                with connection.cursor() as cursor:
                    query = "UPDATE follow set acceptedFollow = 1 WHERE followeeUsername = %s AND followerUsername = %s"
                    cursor.execute(query, (followeeUsername, session["username"]))
            except pymysql.err.IntegrityError:
                error = "You are already following %s or %s doesn't exist ." % (username, username)
                return render_template('follow.html', error=error)    
            return redirect("/follow")  
        else:
            print "haha" 
            try:
                with connection.cursor() as cursor:
                    query = "DELETE from follow WHERE followeeUsername = %s AND followerUsername = %s"
                    cursor.execute(query, (deleteUsername, session["username"]))
            except pymysql.err.IntegrityError:
                error = "An error has occurred"
                return render_template('follow.html', error=error, hider="display:none;")  
            return redirect("/follow")

    error = "An error occurred. Please try again."
    return render_template('follow.html', error=error, hider="display:none;") 
    
if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)

    app.run(debug=True)