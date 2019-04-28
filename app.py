from flask import Flask, render_template, request, session, redirect, url_for, send_file
import os
import string
import random
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time

#flask app
app = Flask(__name__)
app.secret_key = "super secret key"
IMAGES_DIR = os.path.join(os.getcwd(), "images")

#connect to database
connection = pymysql.connect(host="localhost",
                             user="root",
                             password="",
                             db="finstagram",
                             charset="utf8mb4",
                             port=3306,
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg']) #allowed extensions for images

#this function zips multiple data
@app.template_global(name='zip')
def _zip(*args, **kwargs): #to not overwrite builtin zip in globals
    return __builtins__.zip(*args, **kwargs)

#this function checks if the image has the right extension
def allowed_file(filename): #check file extension
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

#this function makes sure the user is logged in to use access certain pages/functions
#login check wrapper
def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if not "username" in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return dec

#route to index file
@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("home"))
    return render_template("index.html")

#route to home file
@app.route("/home")
@login_required
def home():
    filepath = os.path.join(IMAGES_DIR, session["username"], "avatars")
    if not os.path.exists(filepath):
        os.mkdir(os.path.join(IMAGES_DIR, session["username"]))
        os.mkdir(filepath)
    return render_template("home.html", username=session["username"])

#route to upload file
@app.route("/upload", methods=["GET"])
@login_required
def upload():
    return render_template("upload.html")

#route to upload login
@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

#route to register file
@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")

#this function process the data in login form
@app.route("/loginAuth", methods=["POST"])
def loginAuth():
    #get data
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest() #hash password

        #query database to verify user
        with connection.cursor() as cursor:
            query = "SELECT * FROM person WHERE username = %s AND password = %s"
            cursor.execute(query, (username, hashedPassword))
        data = cursor.fetchone()
        if data: #authenticate user
            session["username"] = username
            return redirect(url_for("home"))

        error = "Incorrect username or password."
        return render_template("login.html", error=error) #error

    error = "An unknown error has occurred. Please try again."
    return render_template("login.html", error=error) #error

#this function process the data in register form
@app.route("/registerAuth", methods=["POST"])
def registerAuth():
    #get data from form
    if request.form:
        requestData = request.form
        privFlag = 1
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest() #hash password
        firstName = requestData["fname"]
        lastName = requestData["lname"]
        option = request.form['options']
        bio = requestData["bio"]

        #set public or private account status
        if option == "Public":
            privFlag = 0
        elif option == "Private":
            privFlag = 1

        #create path to user's avatar
        AV_IMAGES_DIR = os.path.join(os.getcwd(), "images", username, "avatars")
    
        if request.files:   
            image_file = request.files.get("av_imageToUpload")
            image_name = image_file.filename
            if not allowed_file(image_name): #verify file extension
                error = "File not recognized"
                return render_template("register.html", error=error)

            filepath = os.path.join(AV_IMAGES_DIR, image_name) #create path

            #insert into database
            try:
                with connection.cursor() as cursor:
                    query = "INSERT INTO person (username, password, fname, lname, avatar, isPrivate, bio) VALUES (%s, %s, %s, %s, %s, %s, %s)"
                    cursor.execute(query, (username, hashedPassword, firstName, lastName, image_name, int(privFlag), bio))
            except pymysql.err.IntegrityError:
                error = "%s is already taken." % (username)
                return render_template('register.html', error=error)    
            
            #create directory
            if not os.path.isdir("images"):
                os.mkdir(IMAGES_DIR)
           
           #create directories
            os.mkdir(os.path.join(os.getcwd(), "images", username))
            os.mkdir(os.path.join(os.getcwd(), "images", username, "avatars"));

            #save image
            image_file.save(filepath)

            return redirect(url_for("login"))

    error = "An error has occurred. Please try again."
    return render_template("register.html", error=error) #error

#route to logout
@app.route("/logout", methods=["GET"])
@login_required
def logout():
    session.pop("username")
    return redirect("/")

#route to upload image
#this function uploads an image
@app.route("/uploadImage", methods=["POST"])
@login_required
def upload_image():

    #get data from form
    if request.form:
        requestData = request.form
        followersFlag = 0
        caption_value = requestData["caption_value"]
        option = request.form["options"]

        #get allFollowers flag
        if option == "Yes":
            followersFlag = 1
        elif option == "No":
            followersFlag = 0

        #if file uploaded
        if request.files:
            image_file = request.files.get("imageToUpload", "")
            image_name = image_file.filename

            #create file path
            filepath = os.path.join(IMAGES_DIR, session["username"], image_name)
            
            #if path already exists, randomize an image name
            if os.path.exists(filepath):
                image_name = os.path.splitext(image_name)[0] + "_" + ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5)) + os.path.splitext(image_name)[1]
                filepath = os.path.join(IMAGES_DIR, session["username"], image_name)
                
            #verify image is a right type
            if allowed_file(image_name):
                #save image
                image_file.save(filepath)
                #insert into database
                query = "INSERT INTO photo (timestamp, filePath, photoOwner, caption, allFollowers) VALUES (%s, %s, %s, %s, %s)"
                with connection.cursor() as cursor:
                    cursor.execute(query, (time.strftime('%Y-%m-%d %H:%M:%S'), image_name, session["username"], caption_value, followersFlag))
                    session["photoID"] = cursor.lastrowid
                message = "Image has been successfully uploaded."
                if followersFlag == 1:
                    #if visible to all followers then return
                    return render_template("upload.html", message=message, hider="display:none;")
                elif followersFlag == 0:
                    #if not visible to all followers, return to close friend group page
                    return redirect("/closeFriendGroups")
            else:
                message = "Failed to upload image."
                return render_template("upload.html", message=message) #error

        else:
            message = "Failed to upload image."
            return render_template("upload.html", message=message) #error

    else:
        message = "Failed to upload image."
        return render_template("upload.html", message=message) #error

#this function displays the images
#route to images
@app.route("/images", methods=["GET"])
@login_required
def images():
    #get image data from database
    query = "SELECT photo.photoID AS ID, timestamp, filePath, photoOwner, caption  FROM photo, belong, share WHERE belong.username = %s AND belong.groupOwner = share.groupOwner AND belong.groupName = share.groupName AND photo.photoID = share.photoID UNION SELECT photo.photoID AS ID, timestamp, filePath, photoOwner, caption FROM photo, follow where photoOwner = %s or (photoOwner = followeeUsername AND followerUsername = %s AND acceptedFollow = 1)"
    with connection.cursor() as cursor:
        cursor.execute(query, (session["username"], session["username"], session["username"]))
    data = cursor.fetchall()

    #get tag and image data from database
    query = "SELECT photo.photoID AS ID, fname, lname FROM photo, tag, person WHERE photo.photoID = tag.photoID AND acceptedTag=1 AND tag.username = person.username"  
    with connection.cursor() as cursor:
        cursor.execute(query)
    tagData = cursor.fetchall()
    if cursor.rowcount == 0: #if no tag data found return
        return render_template("images.html", images=data)
    return render_template("images.html", images=data, tags=tagData) #tag data found

 #route to image src url
@app.route("/image/<owner_name>/<image_name>", methods=["GET"])
@login_required
def image(owner_name, image_name):
    #get image path
    image_location = os.path.join(IMAGES_DIR, owner_name, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg") #return file

#this function lists the close friend groups the user belongs to
#route to close friend group from image upload
@app.route("/closeFriendGroups", methods=["GET"])
@login_required
def getCloseFriendGroups():
    username = session["username"]
    #list close friend groups that the use belongs to
    try:
        with connection.cursor() as cursor:
            query = "SELECT groupName, groupOwner FROM Belong left join (SELECT * FROM Share where photoID=%s) AS T2 using (groupName, groupOwner) WHERE photoID is NULL AND username = %s"
            cursor.execute(query, (session["photoID"], username))
    except pymysql.err.IntegrityError:
        error = "An error has occured"
        return render_template("closeFriendGroups.html", message=error, hider="display:none;")  #error 
    if cursor.rowcount == 0: #if user has no groups they belong to
        error = "%s has no more Close Friend Groups to share photo with." % (username)
        return render_template("closeFriendGroups.html", message=error, hider="display:none;")  

    #if they have groups they belong to
    else:
        values = []
        groupOwners = []
        groupNames = []
        data = cursor.fetchall()
        i = 0
        #send data to html and keep state in session
        for line in data:
            values.append(str(i) + " - GroupName: " + str(line["groupName"]) + " | " + "GroupOwner: " + str(line["groupOwner"]))
            groupOwners.append(str(line["groupOwner"]))
            groupNames.append(str(line["groupName"]))
            i = i + 1
        session["GroupNames"] = groupNames
        session["GroupOwners"] = groupOwners
        return render_template("closeFriendGroups.html", groupsData=values)

#this function is used to share a picture to a close friend group
#process close friend group selected
@app.route("/select_closeFriendsGroup", methods=["GET", "POST"])
@login_required
def select_closeFriendGroups():
    #get data
    if request.form:
        option_data = int(request.form["options"])
        if option_data < len(session["GroupOwners"]): #validate data
            groupOwner =  (session["GroupOwners"])[option_data]
            groupName =  (session["GroupNames"])[option_data]

            #update database
            try:
                with connection.cursor() as cursor:
                    query = "INSERT INTO share (groupName, groupOwner, photoID) VALUES (%s, %s, %s)"
                    cursor.execute(query, (groupName, groupOwner, int(session["photoID"])))
            except pymysql.err.IntegrityError:
                error = "An error has occured"
                return render_template("closeFriendGroups.html", message=error, hider="display:none;") 
            return redirect("/closeFriendGroups") 
        else:
            error = "An error has occured"
            return render_template("closeFriendGroups.html", message=error, hider="display:none;") #error
    else:
        error = "An error has occured"
        return render_template("closeFriendGroups.html", message=error, hider="display:none;") #error   

#this function lists the follow requests sent to the user
#route to follow
@app.route("/follow", methods=["GET"])
@login_required
def follow():
    #list follow requests
    username = session["username"]
    try:
        with connection.cursor() as cursor:
            query = "SELECT * FROM Follow where followeeUsername = %s AND acceptedFollow = 0"
            cursor.execute(query, (username))
    except pymysql.err.IntegrityError:
        error = "An error has occured"
        return render_template('follow.html', error=error, hider="display:none;") #error   
    if cursor.rowcount == 0: #no follow requests
        error = "No follow requests."
        return render_template('follow.html', error=error, hider="display:none;")  
    #if friend requests exist
    else:
        #send data to the html and save state
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

#this function processes the sending of a follow request
#process data for person to follow
@app.route("/followAuth", methods=["POST"])
@login_required
def followAuth():
    #get data from form
    if request.form:
        requestData = request.form
        username = requestData["username"]
        if username == session["username"]:
            error = "You cannot follow yourself"
            return render_template('follow.html', error=error, hider2="display:none;", hider="display:none;") #error  
        #update database
        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO follow (followeeUsername, followerUsername, acceptedFollow) VALUES (%s, %s, 0)"
                cursor.execute(query, (username, session["username"]))
        except pymysql.err.IntegrityError:
            error = "You are already following %s or %s doesn't exist ." % (username, username)
            return render_template('follow.html', error=error, hider2="display:none;", hider="display:none;") #error   
        return redirect("/follow") #sucess
                  
    error = "An error has occurred. Please try again."
    return render_template('follow.html', error=error, hider="display:none;", hider2="display:none;") #error

#process accept and delete follow requests
@app.route("/acceptFollows", methods=["POST"])
@login_required
def acceptfollowAuth():
    flag = 1
    #get data from form
    if request.form:
        option_data =  request.form["options"]
        if not option_data.isdigit(): #validate data
            option_data =  (request.form["options"]).split('-', 1)[0]
            if int(option_data) >= len(session["followValues"]) or not option_data.isdigit(): #validate data
                error = "An error has occurred. Please try again."
                return render_template('follow.html', error=error, hider="display:none;", hider2="display:none;") #error 
            deleteUsername =  (session["followValues"])[int(option_data)] #get usename to delete follower request
            flag = 0
        else: 
            if int(option_data) >= len(session["followValues"]): #validate data
                error = "An error has occurred. Please try again."
                return render_template('follow.html', error=error, hider="display:none;", hider2="display:none;") #error 
            followeeUsername = (session["followValues"])[int(option_data)] #get usename to accept follower request
        #if accept follow request
        if flag:
            #update database
            try:
                with connection.cursor() as cursor:
                    query = "UPDATE follow set acceptedFollow = 1 WHERE followeeUsername = %s AND followerUsername = %s"
                    cursor.execute(query, (session["username"], followeeUsername))
            except pymysql.err.IntegrityError:
                error = "You are already following %s or %s doesn't exist ." % (username, username)
                return render_template('follow.html', error=error, hider2="display:none;", hider="display:none;") #error    
            return redirect("/follow") #success 
        #if delete follow request
        else:
            #update database
            try:
                with connection.cursor() as cursor:
                    query = "DELETE from follow WHERE followeeUsername = %s AND followerUsername = %s"
                    cursor.execute(query, (session["username"], deleteUsername))
            except pymysql.err.IntegrityError:
                error = "An error has occurred"
                return render_template('follow.html', error=error, hider="display:none;", hider2="display:none;") #error  
            return redirect("/follow") #success

    error = "An error occurred. Please try again."
    return render_template('follow.html', error=error, hider="display:none;", hider2="display:none;") #error 

#this function lists tag requests sent to the user    
#route to tags
@app.route("/tags", methods=["GET"])
@login_required
def acceptTag():
    username = session["username"]
    #get tag requests sent to this user
    try:
        with connection.cursor() as cursor:
            query = "SELECT photoOwner, photoID, filePath FROM Tag NATURAL JOIN Photo WHERE username=%s AND acceptedTag=0"
            cursor.execute(query, (username))
    except pymysql.err.IntegrityError:
        error = "An error has occured"
        return render_template('tag.html', error=error, hider="display:none;")  #error  
    if cursor.rowcount == 0:  # no tag requests
        error = "No tag requests."
        return render_template('tag.html', error=error, hider="display:none;") #error 
     #data to send to html and save state
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

#this function process tag accept/delete
@app.route("/acceptTags", methods=["POST"])
@login_required
def acceptTagAuth():
    flag = 1
    #get data from form
    if request.form:
        option_data =  request.form["options"]
        if not option_data.isdigit():  #validate data
            option_data =  (request.form["options"]).split('-', 1)[0]
            if int(option_data) >= len(session["tagPhotoIDs"]) or not option_data.isdigit():  #validate data
                error = "An error has occurred. Please try again."
                return render_template('tag.html', error=error, hider="display:none;") #error
            deleteTagPhotoID =  (session["tagPhotoIDs"])[int(option_data)] #photo ID of the photo tag to delete
            flag = 0
        else: 
            if int(option_data) >= len(session["tagPhotoIDs"]): #validate data
                error = "An error has occurred. Please try again."
                return render_template('tag.html', error=error, hider="display:none;") #error
            acceptTagPhotoID =  (session["tagPhotoIDs"])[int(option_data)] #photo ID of the photo tag to accept
        #accept tag
        #update database
        if flag:
            #update database
            try:
                with connection.cursor() as cursor:
                    query = "UPDATE tag set acceptedTag = 1 WHERE username = %s AND photoID = %s"
                    cursor.execute(query, (session["username"], int(acceptTagPhotoID)))
            except pymysql.err.IntegrityError:
                error = "Already accepted tag."
                return render_template('tag.html', error=error, hider="display:none;") #error    
            return redirect("/tags") #success 
        #delete tag
        else:
            #update database
            try:
                with connection.cursor() as cursor:
                    query = "DELETE from tag WHERE username = %s AND photoID = %s"
                    cursor.execute(query, (session["username"], int(deleteTagPhotoID)))
            except pymysql.err.IntegrityError:
                error = "An error has occurred"
                return render_template('tag.html', error=error, hider="display:none;", hider2="display:none;") #error 
            return redirect("/tags") #success

    error = "An error occurred. Please try again."
    return render_template('tag.html', error=error, hider="display:none;") #error

#route to tag someone page to save state of the photo ID
@app.route("/tagMe/<photoID>", methods=["GET"])
@login_required
def tagMe(photoID):
    session["tagMePhotoID"] = photoID
    return render_template('tagMe.html') 

#this function process data of person to tag
@app.route("/tagMeAuth", methods=["POST"])
@login_required
def tagMeAuth():
    flag = 0
    #get data from form
    if request.form:
        requestData = request.form
        username = requestData["username"] 
        #self tagging
        if username == session["username"]:
            #update database
            try:
                with connection.cursor() as cursor:
                    query = "INSERT INTO tag (username, photoID, acceptedTag) VALUES (%s, %s, 1)"
                    cursor.execute(query, (username, session["tagMePhotoID"]))
            except pymysql.err.IntegrityError:
                error = "%s already tagged ." % (username)
                return render_template('tagMe.html', error=error) #error    
            return redirect("/images") #success
        #not self tagging
        #make sure photo is visible to the person you're tagging them with
        else:
            #query database and get photos the person has access to
            query = "SELECT photo.photoID AS ID FROM photo, belong, share WHERE belong.username = %s AND belong.groupOwner = share.groupOwner AND belong.groupName = share.groupName AND photo.photoID = share.photoID UNION SELECT photo.photoID AS ID FROM photo, follow where photoOwner = %s or (photoOwner = followeeUsername AND followerUsername = %s AND acceptedFollow = 1)"
            with connection.cursor() as cursor:
                cursor.execute(query, (username, username, username))
            if cursor.rowcount == 0: #if the person doesn't exist
                error = "%s doesn't exist." % (username)
                return render_template('tagMe.html', error=error) #error
            data = cursor.fetchall()

            #check if photo is visible to the person you're tagging with
            for line in data:
                print line["ID"]
                if int(session["tagMePhotoID"]) == int(line["ID"]):
                    flag = 1
                    break
            if flag == 1: #if photo was visible
                try:
                    #update database
                    with connection.cursor() as cursor:
                        query = "INSERT INTO tag (username, photoID, acceptedTag) VALUES (%s, %s, 0)"
                        cursor.execute(query, (username, session["tagMePhotoID"]))
                except pymysql.err.IntegrityError:
                    error = "%s already tagged ." % (username)
                    return render_template('tagMe.html', error=error) #error    
                return redirect("/images")
            elif flag == 0:
                #photo isn't visible to the user
                error = "Photo isnt visible to %s" % (username)
                return render_template('tagMe.html', error=error) #error
                      
    error = "An error has occurred. Please try again."
    return render_template('tagMe.html', error=error, hider="display:none;") #error 

#this function lists close friend groups user owns
@app.route("/closefg", methods=["GET"])
@login_required
def closefg():
    username = session["username"]
    #query database
    try:
        with connection.cursor() as cursor:
            query = "SELECT groupName, groupOwner FROM closeFriendGroup WHERE groupOwner = %s"
            cursor.execute(query, (username))
    except pymysql.err.IntegrityError:
        error = "An error has occured"
        return render_template("closefgList.html", message=error, hider="display:none;") #error  
    if cursor.rowcount == 0: #user doesnt own any close friend groups
        error = "%s has owns no Close Friend Groups." % (username)
        return render_template("closefgList.html", message=error, hider="display:none;") #error  
    #user owns a close friend group
    #send data to html file and save state
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

#this function process data of close friend group form for selecting close friend group
@app.route("/closefgChoose", methods=["GET", "POST"])
@login_required
def closefgChoose():
    #get data from form
    if request.form:
        option_data = int(request.form["options"])
        if option_data < len(session["GroupNames"]): #validate data from form
            session["closefgName"] =  (session["GroupNames"])[option_data]
            return render_template("closefgSelect.html", groupName=session["closefgName"]) #success 
        else:
            error = "An error has occured"
            return render_template("closefgList.html", message=error, hider="display:none;") #error 
    else:
        error = "An error has occured"
        return render_template("closefgList.html", message=error, hider="display:none;") #error   

#this function process data of username to add to selected close friend group
@app.route("/closefgChooseAuth", methods=["POST"])
@login_required
def closefgChooseAuth():
    #get data
    if request.form:
        requestData = request.form
        username = requestData["username"]
        if username == session["username"]: #if username is the owner
            error = "You are already in the group you own"
            return render_template('closefgList.html', message=error, hider="display:none;") #error  
        try:
            #update database
            with connection.cursor() as cursor:
                query = "INSERT INTO Belong (groupName, groupOwner, username) VALUES (%s, %s, %s)"
                cursor.execute(query, (session["closefgName"], session["username"], username))
        except pymysql.err.IntegrityError:
            error = "%s is already in %s or doesn't exist." % (username, session["closefgName"])
            return render_template('closefgList.html', message=error, hider="display:none;") #error      
        error = "Sucess"
        return render_template('closefgList.html', message=error, hider="display:none;") #success   
                  
    error = "An error has occurred. Please try again."
    return render_template('closefgList.html', message=error, hider="display:none;") #error 

if __name__ == "__main__":
    if not os.path.isdir("images"): #create images directory if it doesn't exist
        os.mkdir(IMAGES_DIR)

    app.run(debug=True)