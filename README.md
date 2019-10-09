DEFINITION:  
* Package (AIP) = "as-submitted" directory containing the content information and preservation description information generated upon digitization of one or more media items.  
* Package (AIP) = finalized directory with structured/fleshed-out content information (in "objects" folder) and preservation description information (in "metadata" folder) for one media item (e.g. one tape or one film).  
* Collection = parent directory containing all packages that belong to the same contributor. Collections are grouped by last name and can encompass any number of format of media item.  
* Name_Of_Event and Digitization_Location = NMAAHC digitizes both in-house and on the road. This package structure groups files by where they were created.  
  
  
===== PROPOSED AIP DIRECTORY STRUCTURE =====  
  
├── Digitization_Location  
│   ├── Name_Of_Event  
│   │   ├── Collection name: SC0001_YYYYMMDD_LASTNAME1  
│   │   │   ├── AIP name: SC0001_YYYYMMDD_LASTNAME1_FORMAT_ITEM#  
│   │   │   │   ├── objects  
│   │   │   │   │   └── videofiles.xyz  
│   │   │   │   └── metadata  
│   │   │   │   │   └── metadatafiles.xyz  
│   │   ├── Collection name: SC0001_YYYYMMDD_LASTNAME2  
│   │   │   ├── AIP name: SC0001_YYYYMMDD_LASTNAME2_FORMAT_ITEM#  
│   │   │   │   ├── objects  
│   │   │   │   │   └── videofiles.xyz  
│   │   │   │   └── metadata  
│   │   │   │   │   └── metadatafiles.xyz  
  
Example AIP structures from SIPs below:  
├── Chicago  
│   ├── 01_CommunityCuration  
│   │   ├── SC0001_YYYYMMDD_LASTNAME1  
│   │   │   ├── SC0001_YYYYMMDD_LASTNAME1_S8_01_03  
│   │   │   │   ├── objects  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME1_S8_01_03.mp4  
│   │   │   │   │   └── SC0001_YYYYMMDD_LASTNAME1_S8_01_03.mov  
│   │   │   │   ├── metadata  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME1_S8_01_03.ffprobe.xml  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME1_S8_01_03.mediainfo.xml  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME1_S8_01_03.mediatrace.xml  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME1_S8_01_03.exiftool.xml  
│   │   │   │   │   └── SC0001_YYYYMMDD_LASTNAME1_S8_01_03.md5  
│   │   ├── SC0001_YYYYMMDD_LASTNAME2  
│   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_01  
│   │   │   │   ├── objects  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_01.mkv  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_01.mp4  
│   │   │   │   ├── metadata  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_01.framemd5  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_01.ffprobe.xml  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_01.mediainfo.xml  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_01.mediatrace.xml  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_01.exiftool.xml  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_01.mkv.qctools.xml.gz  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_01_QC_output_graphs.jpeg  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_01_capture_options.log  
│   │   │   │   │   └── SC0001_YYYYMMDD_LASTNAME2_VHS_01_ffmpeg_decklink_input.log  
│   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_05  
│   │   │   │   ├── objects  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_05.mkv  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_05.mp4  
│   │   │   │   ├── metadata  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_05.framemd5  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_05.ffprobe.xml  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_05.mediainfo.xml  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_05.mediatrace.xml  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_05.exiftool.xml  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_05.mkv.qctools.xml.gz  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_05_QC_output_graphs.jpeg  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_05_capture_options.log  
│   │   │   │   │   └── SC0001_YYYYMMDD_LASTNAME2_VHS_05_ffmpeg_decklink_input.log  
│   │   ├── SC0001_YYYYMMDD_LASTNAME3  
│   │   │   ├── SC0001_YYYYMMDD_LASTNAME3_MiniDV_02  
│   │   │   │   ├── objects  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME3_MiniDV_02.mov  
│   │   │   │   │   └── SC0001_YYYYMMDD_LASTNAME3_MiniDV_02.mp4  
│   │   │   │   ├── metadata  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME3_MiniDV_02.md5  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME3_MiniDV_02.ffprobe.xml  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME3_MiniDV_02.mediainfo.xml  
│   │   │   │   │   ├── SC0001_YYYYMMDD_LASTNAME3_MiniDV_02.mediatrace.xml  
│   │   │   │   │   └── SC0001_YYYYMMDD_LASTNAME3_MiniDV_02.exiftool.xml  
  
  
  
===== CURRENT SIP STRUCTURES =====  
MEDIA TYPE / source format / provenance  
  
*** FILM / analog / digitized in-house ***  
TK: DPX package example  
  
*** FILM / analog / digitized on-location ***  
  
Digitization_Location  
├── Name_Of_Event  
│   ├── YYYYMMDD  
│   │   └── SC0001_YYYYMMDD_LASTNAME  
│   │     ├── S8_01_03  
│   │     │   ├── MP4_2048x1152  
│   │     │   │   └── SC0001_YYYYMMDD_LASTNAME1_S8_01_03.mp4  
│   │     │   └── ProRes_2048x1536  
│   │     │       └── SC0001_YYYYMMDD_LASTNAME1_S8_01_03.mov  
│   │     └── SC0001_YYYYMMDD_LASTNAME.cdir  
  
Naming:  
Collection directory:       SC0001_YYYYMMDD_LASTNAME                = CODE_YYYYMMDD_LASTNAME  
Package name:               S8_01_03                                = ANALOGFORMATCODE_OBJECT#_OBJECT#2  
Derivative subdirectory:    MP4_2048x1152                           = DIGITIZEDFORMATCODE_WIDTHxHEIGHT  
Filename (derivative?):     SC0001_YYYYMMDD_LASTNAME1_S8_01_03.mov  = COLLECTIONNAME_PACKAGENAME.extension  
  
  
*** VIDEO / analog / digitized on-location ***  
  
Digitization_Location  
├── Name_Of_Event  
│   ├── YYYYMMDD  
│   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_01  
│   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_01.framemd5  
│   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_01.mkv  
│   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_01.mkv.qctools.xml.gz  
│   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_01.mp4  
│   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_01_QC_output_graphs.jpeg  
│   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_01_capture_options.log  
│   │   │   └── SC0001_YYYYMMDD_LASTNAME2_VHS_01_ffmpeg_decklink_input.log  
│   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_05  
│   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_05.framemd5  
│   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_05.mkv  
│   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_05.mkv.qctools.xml.gz  
│   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_05.mp4  
│   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_05_QC_output_graphs.jpeg  
│   │   │   ├── SC0001_YYYYMMDD_LASTNAME2_VHS_05_capture_options.log  
│   │   │   └── SC0001_YYYYMMDD_LASTNAME2_VHS_05_ffmpeg_decklink_input.log  
  
Naming:  
Collection directory:       n/a  
Package name:               SC0001_YYYYMMDD_LASTNAME2_VHS_01        = CODE_YYYYMMDD_LASTNAME_ORIGINALFORMATCODE_OBJECT#  
Filename (master):          SC0001_YYYYMMDD_LASTNAME2_VHS_01.mkv    = PACKAGENAME.extension  
Derivative subdirectory:    n/a  
  
  
*** VIDEO / DV / transferred on-location ***  
  
Digitization_Location  
├── Name_Of_Event  
│   ├── SC0001_YYYYMMDD_LASTNAME  
│   │   ├── SC0001_YYYYMMDD_LASTNAME3_MiniDV_02_TITLEOFTAPE  
│   │   │   ├── SC0001_YYYYMMDD_LASTNAME3_MiniDV_02_TITLEOFTAPE.mov  
│   │   │   ├── SC0001_YYYYMMDD_LASTNAME3_MiniDV_02_TITLEOFTAPE_YYYYMMDD_checksums.md5  
│   │   │   └── derivative  
│   │   │       └── SC0001_YYYYMMDD_LASTNAME3_MiniDV_02_TITLEOFTAPE.mp4  
│   ├── SC0001_YYYYMMDD_LASTNAME_MiniDV_04_TITLEOFTAPE  
│   │   │   ├── SC0001_YYYYMMDD_LASTNAME_MiniDV_04_TITLEOFTAPE.mov  
│   │   │   ├── SC0001_YYYYMMDD_LASTNAME_MiniDV_04_TITLEOFTAPE_YYYYMMDD_checksums.md5  
│   │   │   └── derivative  
│   │   │       └── SC0001_YYYYMMDD_LASTNAME_MiniDV_04_TITLEOFTAPE.mp4  
  
Filenaming:  
Collection directory:       SC0001_YYYYMMDD_LASTNAME                             = CODE_YYYYMMDD_LASTNAME  
Package name:               SC0001_YYYYMMDD_LASTNAME3_MiniDV_02_TITLEOFTAPE      = COLLECTIONNAME_ORIGINALFORMATCODE_OBJECT#_OBJECTTITLE  
Master filename:            SC0001_YYYYMMDD_LASTNAME3_MiniDV_02_TITLEOFTAPE.mov  = COLLECTIONNAME_PACKAGENAME.extension  
Derivative subdirectory:    derivative                                           = derivative  
