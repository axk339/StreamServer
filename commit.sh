#!/bin/bash

msg=$1
if [ "$msg" = "" ]; then
	msg="no details"
fi
echo "Commit Message: $msg"

echo "* Checking [root]"
git commit -a -m "$msg"
git push origin main
#echo "Local repository, no push"


