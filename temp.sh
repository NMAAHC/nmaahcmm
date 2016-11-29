#!/bin/bash

# “a” and “arga” have optional arguments with default values.
# “b” and “argb” have no arguments, acting as sort of a flag.
# “c” and “argc” have required arguments.

# set an initial value for the flag
ARG_B=0

# read the options
TEMP=`getopt -o a::bc: --long arga::,argb,argc: -n 'test.sh' -- "$@"`
eval set -- "$TEMP"

# extract options and their arguments into variables.
while true ; do
    case "$1" in
        -a|--arga)
            case "$2" in
                "") ARG_A='some default value' ; shift 2 ;;
                *) ARG_A=$2 ; shift 2 ;;
            esac ;;
        -b|--argb) ARG_B=1 ; shift ;;
        -c|--argc)
            case "$2" in
                "") shift 2 ;;
                *) ARG_C=$2 ; shift 2 ;;
            esac ;;
        --) shift ; break ;;
        *) echo "Internal error!" ; exit 1 ;;
    esac
done

# do something with the variables -- in this case the lamest possible one :-)
echo "ARG_A = $ARG_A"
echo "ARG_B = $ARG_B"
echo "ARG_C = $ARG_C"