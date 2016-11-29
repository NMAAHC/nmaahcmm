#!/bin/bash
LIST='find . -type f'

for FILE in $LIST;
do
	md5 $FILE >> FILE.txt
done

exit 0