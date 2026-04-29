# -------------------------------------------------------
# BASE IMAGE
# We start from an official Python 3.12 image
# Think of this as a clean Linux computer with
# Python already installed
# -------------------------------------------------------
FROM python:3.12-slim

# -------------------------------------------------------
# SET WORKING DIRECTORY
# All commands will run from this folder inside
# the container. Like doing "cd /app" first.
# -------------------------------------------------------
WORKDIR /app

# -------------------------------------------------------
# COPY REQUIREMENTS FIRST
# We copy requirements.txt before the rest of the code
# This is a Docker best practice — if your code changes
# but requirements don't, Docker uses cached packages
# and builds much faster
# -------------------------------------------------------
COPY requirements.txt .

# -------------------------------------------------------
# INSTALL DEPENDENCIES
# pip install all packages listed in requirements.txt
# --no-cache-dir means don't store pip cache
# keeps the image smaller
# -------------------------------------------------------
RUN pip install --no-cache-dir -r requirements.txt

# -------------------------------------------------------
# COPY PROJECT FILES
# Now copy all your project files into the container
# The . . means "copy everything from current folder
# to current folder inside container (/app)"
# -------------------------------------------------------
COPY . .

# -------------------------------------------------------
# EXPOSE PORT
# Tell Docker your app runs on port 8000
# This does not publish the port — just documents it
# -------------------------------------------------------
EXPOSE 8000

# -------------------------------------------------------
# START COMMAND
# This command runs when the container starts
# --host 0.0.0.0 means accept connections from outside
# the container (required for Docker networking)
# -------------------------------------------------------
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
