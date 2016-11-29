#!/bin/bash

for file in "$1"/*PM.mov ; do 
	ffmpeg -i "$file" -an -f framemd5 "${file}.framemd5.txt"
done
