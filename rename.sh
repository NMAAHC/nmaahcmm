#!/usr/bin/env bash

for i in $1 ; do 
	rename s/__/_/ 
	echo $i 

done