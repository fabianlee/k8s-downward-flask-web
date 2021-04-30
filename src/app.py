#!/usr/bin/env python
#
# Takes metadata passed on by Kubernetes Downward API
# shows environment variables and volume mounts
#

import os
import io
import logging
from flask import Flask, request, jsonify
from multiprocessing import Value

# log level mutes every request going to stdout
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
app = Flask(__name__)

# version and build string placed into env by Docker ENV
version_str = ""
buildtime_str = ""

# env keys set by k8s
k8s_downward_env_list = [
  "MY_NODE_NAME","MY_POD_NAME","MY_POD_IP","MY_POD_SERVICE_ACCOUNT",
  "MY_POD_LABEL_APP","MY_POD_ANNOTATION_AUTHOR","MY_POD_MEM_LIMIT_MB",
  "MY_POD_MEM_REQUEST_MB"
  ]

# global request counter
# https://stackoverflow.com/questions/42680357/increment-counter-for-every-access-to-a-flask-view
counter = Value('i', 0)

# https://riptutorial.com/flask/example/19420/catch-all-route
# catches both / and then all other
@app.route('/', defaults={'upath': ''})
@app.route("/<path:upath>")
def entry_point(upath):
    """ delivers HTTP response """

    # check for valid app_context
    upath = "/" + upath
    print("Request to {}".format(upath))
    if not upath.startswith(app_context):
      return app.response_class("404 only configured to deliver from {}".format(app_context),status=404,mimetype="text/plain") 

    # increment request counter
    with counter.get_lock():
        requestcount = counter.value
        counter.value += 1

    # create buffered response
    buffer = io.StringIO()
    buffer.write( "{} {} {}\n".format(requestcount,request.method,request.path) )
    buffer.write( "path: {}\n".format(request.path) )
    buffer.write( "Host: {}\n".format(request.headers.get('Host') ))

    # check for env values from downward API
    for keyname in k8s_downward_env_list:
        buffer.write ( "ENV {} = {}\n".format(keyname, os.getenv(keyname,"none")) )

    # check /etc/podinfo for Downward API files
    path="/etc/podinfo/"
    try:
      files = os.listdir(path)
      for f in files:
        fullname=os.path.join(path,f)
        if os.path.isfile(fullname):
          with open(fullname) as f:
            content = f.readlines()
            buffer.write ( "FILE {} = {}\n".format(fullname,content) )
    except FileNotFoundError as fexc:
      print("error while looking for files in path {}".format(fexc))
    except Exception as e:
      print("some kind of error occured! {}".format(e))
    
    return app.response_class(buffer.getvalue(), status=200, mimetype="text/plain")


@app.route("/healthz")
def health():
    """ kubernetes health endpoint """
    return jsonify(
        { 'health':'ok','Version':version_str, 'BuildTime':buildtime_str }
    )

# https://stackoverflow.com/questions/15562446/how-to-stop-flask-application-without-using-ctrl-c
def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    
@app.route('/shutdown', methods=['GET'])
def shutdown():
    shutdown_server()
    return 'Server shutting down...'


if __name__ == '__main__' or __name__ == "main":

    debugVal = bool(os.getenv("DEBUG",False))
    # avoids error with jsonify that checks request.is_xhr
    # https://github.com/pallets/flask/issues/2549
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

    version_str = os.getenv("MY_VERSION","none")
    buildtime_str = os.getenv("MY_BUILDTIME","none")
    print("build version/time: {}/{}".format(version_str,buildtime_str))

    app_context = os.getenv("APP_CONTEXT","/")
    print("app context: {}".format(app_context))

    port = int(os.getenv("PORT", 8000))
    print("Starting web server on port {}".format(port))

    # look for env values from K8S Downward API
    for keyname in k8s_downward_env_list:
        print("ENV {} = {}\n".format(keyname, os.getenv(keyname,"none")) )

    # look for K8S Downward API info in volume mount
    print("files in /etc/podinfo/:")
    try: 
      files = os.listdir("/etc/podinfo/")
      for f in files:
        print(f)
    except FileNotFoundError as fexc:
      print("no files in /etc/podinfo/",e)

    app.run(debug=debugVal, host='0.0.0.0', port=port)


