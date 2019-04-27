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

@app.template_global(name='zip')
def _zip(*args, **kwargs): #to not overwrite builtin zip in globals
    return __builtins__.zip(*args, **kwargs)

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
    filepath = os.path.join(IMAGES_DIR, session["username"], "avatars")
    if not os.path.exists(filepath):
        os.mkdir(os.path.join(IMAGES_DIR, session["username"]))
        os.mkdir(filepath)
    return render_template("home.html", username=session["username"])

@app.route("/upload", methods=["GET"])
@login_required
def upload():
    return render_template("upload.html")

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
@login_required
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
        
            if os.path.exists(filepath):
                image_name = os.path.splitext(image_name)[0] + "_" + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5)) + os.path.splitext(image_name)[1]
                filepath = os.path.join(IMAGES_DIR, session["username"], image_name)
                

            if allowed_file(image_name):
                image_file.save(filepath)
                query = "INSERT INTO photo (timestamp, filePath, photoOwner, caption, allFollowers) VALUES (%s, %s, %s, %s, %s)"
                with connection.cursor() as cursor:
                    cursor.execute(query, (time.strftime('%Y-%m-%d %H:%M:%S'), image_name, session["username"], caption_value, 66))
                    session["photoID"] = cursor.lastrowid
                message = "Image has been successfully uploaded."
                if followersFlag == 1:
                    return render_template("upload.html", message=message, hider="display:none;")
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

@app.route("/images", methods=["GET"])
@login_required
def images():
    query = "SELECT photo.photoID AS ID, timestamp, filePath, photoOwner, caption  FROM photo, belong, share WHERE belong.username = %s AND belong.groupOwner = share.groupOwner AND belong.groupName = share.groupName AND photo.photoID = share.photoID UNION SELECT photo.photoID AS ID, timestamp, filePath, photoOwner, caption FROM photo, follow where photoOwner = %s or (photoOwner = followeeUsername AND followerUsername = %s AND acceptedFollow = 1)"
    with connection.cursor() as cursor:
        cursor.execute(query, (session["username"], session["username"], session["username"]))
    data = cursor.fetchall()

    query = "SELECT photo.photoID AS ID, fname, lname FROM photo, tag, person WHERE photo.photoID = tag.photoID AND acceptedTag=1 AND tag.username = person.username"  
    with connection.cursor() as cursor:
        cursor.execute(query)
    tagData = cursor.fetchall()
    if cursor.rowcount == 0:
        return render_template("images.html", images=data)
    return render_template("images.html", images=data, tags=tagData)

@app.route("/image/<owner_name>/<image_name>", methods=["GET"])
@login_required
def image(owner_name, image_name):
    image_location = os.path.join(IMAGES_DIR, owner_name, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg")

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
            if request.form:
                try:
                    with connection.cursor() as cursor:
                        query = "INSERT INTO share (groupName, groupOwner, photoID) VALUES (%s, %s, %s)"
                        cursor.execute(query, (groupName, groupOwner, int(session["photoID"])))
                except pymysql.err.IntegrityError:
                    error = "An error has occured"
                    return render_template("closeFriendGroups.html", message=error, hider="display:none;") 
                return redirect("/closeFriendGroups")
            error = "An error has occured"
            return render_template("closeFriendGroups.html", message=error, hider="display:none;")  
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
            query = "SELECT * FROM Follow where followeeUsername = %s AND acceptedFollow = 0"
            cursor.execute(query, (username))
    except pymysql.err.IntegrityError:
        error = "An error has occured"
        return render_template('follow.html', error=error, hider="display:none;")   
    if cursor.rowcount == 0:
        error = "No follow requests."
        return render_template('follow.html', error=error, hider="display:none;")  
    else:
        values = []
        followerUsernames = []
        data = cursor.fetchall()
        i = 0
        for line in data:
            followerUsernames.append(str(i) + " - " + str(line["followerUsername"]))
            values.append(str(line["followerUsername"]))
            i = i + 1
        session["followValues"] = values
        session["followerUsernames"] = followerUsernames
        return render_template("follow.html", followData=followerUsernames, error="Follow requests to accept")

@app.route("/followAuth", methods=["POST"])
@login_required
def followAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        if username == session["username"]:
            error = "You cannot follow yourself"
            return render_template('follow.html', error=error, hider2="display:none;", hider="display:none;")  
        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO follow (followeeUsername, followerUsername, acceptedFollow) VALUES (%s, %s, 0)"
                cursor.execute(query, (username, session["username"]))
        except pymysql.err.IntegrityError:
            error = "You are already following %s or %s doesn't exist ." % (username, username)
            return render_template('follow.html', error=error, hider2="display:none;", hider="display:none;")    
        error = "Sucess"
        return redirect("/follow")  
                  
    error = "An error has occurred. Please try again."
    return render_template('follow.html', error=error, hider="display:none;", hider2="display:none;") 

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
                return render_template('follow.html', error=error, hider="display:none;", hider2="display:none;") 
            deleteUsername =  (session["followValues"])[int(option_data)]
            flag = 0
        else: 
            if int(option_data) >= len(session["followValues"]):
                error = "An error has occurred. Please try again."
                return render_template('follow.html', error=error, hider="display:none;", hider2="display:none;") 
            followeeUsername = (session["followValues"])[int(option_data)]
        if flag:
            try:
                with connection.cursor() as cursor:
                    query = "UPDATE follow set acceptedFollow = 1 WHERE followeeUsername = %s AND followerUsername = %s"
                    cursor.execute(query, (session["username"], followeeUsername))
            except pymysql.err.IntegrityError:
                error = "You are already following %s or %s doesn't exist ." % (username, username)
                return render_template('follow.html', error=error, hider2="display:none;", hider="display:none;")    
            return redirect("/follow")  
        else:
            try:
                with connection.cursor() as cursor:
                    query = "DELETE from follow WHERE followeeUsername = %s AND followerUsername = %s"
                    cursor.execute(query, (session["username"], deleteUsername))
            except pymysql.err.IntegrityError:
                error = "An error has occurred"
                return render_template('follow.html', error=error, hider="display:none;", hider2="display:none;")  
            return redirect("/follow")

    error = "An error occurred. Please try again."
    return render_template('follow.html', error=error, hider="display:none;", hider2="display:none;") 
    

@app.route("/tags", methods=["GET"])
@login_required
def acceptTag():
    username = session["username"]
    try:
        with connection.cursor() as cursor:
            query = "SELECT photoOwner, photoID, filePath FROM Tag NATURAL JOIN Photo WHERE username=%s AND acceptedTag=0"
            cursor.execute(query, (username))
    except pymysql.err.IntegrityError:
        error = "An error has occured"
        return render_template('tag.html', error=error, hider="display:none;")   
    if cursor.rowcount == 0:
        error = "No tag requests."
        return render_template('tag.html', error=error, hider="display:none;")  
    else:
        tagPhotoIDs = []
        tagPhotoOwners = []
        indicies = []
        filePaths = []
        data = cursor.fetchall()
        i = 0
        for line in data:
            tagPhotoIDs.append(str(line["photoID"]))
            tagPhotoOwners.append(str(line["photoOwner"]))
            filePaths.append(str(line["filePath"]))
            indicies.append(str(i))
            i = i + 1
        session["tagPhotoIDs"] = tagPhotoIDs
        return render_template("tag.html", error="Tag requests to accept", iD_owner_path_index=zip(tagPhotoIDs,tagPhotoOwners,filePaths,indicies))


@app.route("/acceptTags", methods=["POST"])
@login_required
def acceptTagAuth():
    flag = 1
    if request.form:
        option_data =  request.form["options"]
        if not option_data.isdigit():
            option_data =  (request.form["options"]).split('-', 1)[0]
            if int(option_data) >= len(session["tagPhotoIDs"]) or not option_data.isdigit():
                error = "An error has occurred. Please try again."
                return render_template('tag.html', error=error, hider="display:none;") 
            deleteTagPhotoID =  (session["tagPhotoIDs"])[int(option_data)]
            flag = 0
        else: 
            if int(option_data) >= len(session["tagPhotoIDs"]):
                error = "An error has occurred. Please try again."
                return render_template('tag.html', error=error, hider="display:none;") 
            acceptTagPhotoID =  (session["tagPhotoIDs"])[int(option_data)]
        if flag:
            try:
                with connection.cursor() as cursor:
                    query = "UPDATE tag set acceptedTag = 1 WHERE username = %s AND photoID = %s"
                    cursor.execute(query, (session["username"], int(acceptTagPhotoID)))
            except pymysql.err.IntegrityError:
                error = "Already accepted tag."
                return render_template('tag.html', error=error, hider="display:none;")    
            return redirect("/tags")  
        else:
            try:
                with connection.cursor() as cursor:
                    query = "DELETE from tag WHERE username = %s AND photoID = %s"
                    cursor.execute(query, (session["username"], int(deleteTagPhotoID)))
            except pymysql.err.IntegrityError:
                error = "An error has occurred"
                return render_template('tag.html', error=error, hider="display:none;", hider2="display:none;")  
            return redirect("/tags")

    error = "An error occurred. Please try again."
    return render_template('tag.html', error=error, hider="display:none;") 
   
@app.route("/tagMe/<photoID>", methods=["GET"])
@login_required
def tagMe(photoID):
    session["tagMePhotoID"] = photoID
    return render_template('tagMe.html') 

@app.route("/tagMeAuth", methods=["POST"])
@login_required
def tagMeAuth():
    flag = 0
    if request.form:
        requestData = request.form
        username = requestData["username"] 
        if username == session["username"]:
            try:
                with connection.cursor() as cursor:
                    query = "INSERT INTO tag (username, photoID, acceptedTag) VALUES (%s, %s, 1)"
                    cursor.execute(query, (username, session["tagMePhotoID"]))
            except pymysql.err.IntegrityError:
                error = "%s already tagged ." % (username)
                return render_template('tagMe.html', error=error)    
            return redirect("/images")
        else:
            query = "SELECT photo.photoID AS ID FROM photo, belong, share WHERE belong.username = %s AND belong.groupOwner = share.groupOwner AND belong.groupName = share.groupName AND photo.photoID = share.photoID UNION SELECT photo.photoID AS ID FROM photo, follow where photoOwner = %s or (photoOwner = followeeUsername AND followerUsername = %s AND acceptedFollow = 1)"
            with connection.cursor() as cursor:
                cursor.execute(query, (username, username, username))
            if cursor.rowcount == 0:
                error = "%s doesn't exist." % (username)
                return render_template('tagMe.html', error=error)
            data = cursor.fetchall()

            for line in data:
                print line["ID"]
                if int(session["tagMePhotoID"]) == int(line["ID"]):
                    flag = 1
                    break
            if flag == 1:
                try:
                    with connection.cursor() as cursor:
                        query = "INSERT INTO tag (username, photoID, acceptedTag) VALUES (%s, %s, 0)"
                        cursor.execute(query, (username, session["tagMePhotoID"]))
                except pymysql.err.IntegrityError:
                    error = "%s already tagged ." % (username)
                    return render_template('tagMe.html', error=error)    
                return redirect("/images")
            elif flag == 0:
                error = "Photo isnt visible to %s" % (username)
                return render_template('tagMe.html', error=error)
                      
    error = "An error has occurred. Please try again."
    return render_template('tagMe.html', error=error, hider="display:none;") 

@app.route("/closefg", methods=["GET"])
@login_required
def closefg():
    username = session["username"]
    try:
        with connection.cursor() as cursor:
            query = "SELECT groupName, groupOwner FROM closeFriendGroup WHERE groupOwner = %s"
            cursor.execute(query, (username))
    except pymysql.err.IntegrityError:
        error = "An error has occured"
        return render_template("closefgList.html", message=error, hider="display:none;")  
    if cursor.rowcount == 0:
        error = "%s has owns no Close Friend Groups." % (username)
        return render_template("closefgList.html", message=error, hider="display:none;")  

    else:
        values = []
        groupNames = []
        data = cursor.fetchall()
        i = 0
        for line in data:
            values.append(str(i) + " - GroupName: " + str(line["groupName"]))
            groupNames.append(str(line["groupName"]))
            i = i + 1
        session["GroupNames"] = groupNames
        session["GroupValues"] = values
        return render_template("closefgList.html", groupsData=values)

@app.route("/closefgChoose", methods=["GET", "POST"])
@login_required
def closefgChoose():
    if request.form:
        option_data = int(request.form["options"])
        if option_data < len(session["GroupNames"]):
            session["closefgName"] =  (session["GroupNames"])[option_data]
            return render_template("closefgSelect.html", groupName=session["closefgName"]) 
        else:
            error = "An error has occured"
            return render_template("closefgList.html", message=error, hider="display:none;")  
    else:
        error = "An error has occured"
        return render_template("closefgList.html", message=error, hider="display:none;")   

@app.route("/closefgChooseAuth", methods=["POST"])
@login_required
def closefgChooseAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        if username == session["username"]:
            error = "You are already in the group you own"
            return render_template('closefgList.html', message=error, hider="display:none;")  
        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO Belong (groupName, groupOwner, username) VALUES (%s, %s, %s)"
                cursor.execute(query, (session["closefgName"], session["username"], username))
        except pymysql.err.IntegrityError:
            error = "%s is already in %s or doesn't exist." % (username, session["closefgName"])
            return render_template('closefgList.html', message=error, hider="display:none;")      
        error = "Sucess"
        return render_template('closefgList.html', message=error, hider="display:none;")   
                  
    error = "An error has occurred. Please try again."
    return render_template('closefgList.html', message=error, hider="display:none;") 

if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)

    app.run(debug=True)