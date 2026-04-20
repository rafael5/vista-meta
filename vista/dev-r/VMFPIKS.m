VMFPIKS ;vista-meta — PIKS classification at field level
 ;Spec: docs/vista-meta-spec-v0.4.md § 11
 ;RUNS IN: container, as vehu
 ;
 ;Classifies every field with:
 ;  field_piks: inherited from parent file's PIKS
 ;  ref_piks:   for pointer fields, the target file's PIKS
 ;  cross_piks: Y if field_piks != ref_piks (cross-category reference)
 ;  sensitivity_flag: Y if field name suggests protected data in non-P file
 ;
 ;Requires: piks.tsv (from VMPIKS) to exist
 ;
 ;Usage: D RUN^VMFPIKS   (writes field-piks.tsv)
 ;       D STATS^VMFPIKS (summary)
 ;
 Q
 ;
RUN ;Classify fields and write TSV
 N FPIKS  ; FPIKS(file#)=PIKS category from piks.tsv
 ;
 ; Load file-level PIKS from piks.tsv via ^TMP
 D LOADPIKS(.FPIKS)
 W "Loaded ",$O(FPIKS(""),-1)," file PIKS classifications",!
 ;
 ; Write output
 N PATH S PATH="/home/vehu/export/data-model/field-piks.tsv"
 O PATH:NEWVERSION U PATH
 ;
 ; Header
 W "file_number",$C(9)
 W "field_number",$C(9)
 W "field_name",$C(9)
 W "data_type",$C(9)
 W "file_piks",$C(9)
 W "pointer_target",$C(9)
 W "ref_piks",$C(9)
 W "cross_piks",$C(9)
 W "sensitivity_flag",!
 ;
 N FILE,FLD,TOTAL,CROSSCNT,SENSCNT
 S FILE="",TOTAL=0,CROSSCNT=0,SENSCNT=0
 F  S FILE=$O(^DD(FILE)) Q:FILE=""  Q:FILE'=+FILE  D
 . N FILEPIKS S FILEPIKS=$G(FPIKS(FILE))
 . I FILEPIKS="" S FILEPIKS=$G(FPIKS($$TOPPAR(FILE)))  ; try top parent
 . ;
 . S FLD=""
 . F  S FLD=$O(^DD(FILE,FLD)) Q:FLD=""  Q:FLD'=+FLD  D
 . . Q:'$D(^DD(FILE,FLD,0))
 . . S TOTAL=TOTAL+1
 . . N FNAME,DTYPE,TARG,REFPIKS,CROSS,SENS
 . . S FNAME=$P(^DD(FILE,FLD,0),"^",1)
 . . S DTYPE=$$GETTYPE($P(^DD(FILE,FLD,0),"^",2))
 . . S TARG=$$GETPTARG($P(^DD(FILE,FLD,0),"^",2))
 . . ;
 . . ; Reference PIKS (pointer target)
 . . S REFPIKS=""
 . . I TARG'="" S REFPIKS=$G(FPIKS(TARG))
 . . ;
 . . ; Cross-PIKS flag
 . . S CROSS=""
 . . I REFPIKS'="",FILEPIKS'="",REFPIKS'=FILEPIKS S CROSS="Y",CROSSCNT=CROSSCNT+1
 . . ;
 . . ; Sensitivity flag: protected-data field in non-P file
 . . S SENS=""
 . . I FILEPIKS'="P",FILEPIKS'="" D
 . . . N UFN S UFN=$$UP(FNAME)
 . . . I UFN["SSN"!(UFN["SOCIAL SECURITY") S SENS="Y"
 . . . I UFN["DATE OF BIRTH"!(UFN="DOB") S SENS="Y"
 . . . I UFN["MAIDEN"!(UFN["MOTHER") S SENS="Y"
 . . . I UFN["HOME PHONE"!(UFN["CELL PHONE") S SENS="Y"
 . . . I UFN["HOME ADDRESS"!(UFN["STREET") S SENS="Y"
 . . . I UFN="NAME",FLD=.01 S SENS="Y"  ; .01 NAME in person-like files
 . . I SENS="Y" S SENSCNT=SENSCNT+1
 . . ;
 . . ; Output
 . . W FILE,$C(9),FLD,$C(9),$$ESC(FNAME),$C(9),DTYPE,$C(9)
 . . W FILEPIKS,$C(9),TARG,$C(9),REFPIKS,$C(9),CROSS,$C(9),SENS,!
 ;
 C PATH
 U $P
 W !,"Written to ",PATH,!
 W "  Total fields:        ",TOTAL,!
 W "  Cross-PIKS pointers: ",CROSSCNT,!
 W "  Sensitivity flags:   ",SENSCNT,!
 D XSTATS(.FPIKS)
 Q
 ;
XSTATS(FPIKS) ;Cross-PIKS statistics from in-memory data
 ; Count cross-PIKS patterns by re-walking ^DD
 N FILE,FLD,XPAT
 S FILE=""
 F  S FILE=$O(^DD(FILE)) Q:FILE=""  Q:FILE'=+FILE  D
 . N FP S FP=$G(FPIKS(FILE))
 . I FP="" S FP=$G(FPIKS($$TOPPAR(FILE)))
 . Q:FP=""
 . S FLD=""
 . F  S FLD=$O(^DD(FILE,FLD)) Q:FLD=""  Q:FLD'=+FLD  D
 . . Q:'$D(^DD(FILE,FLD,0))
 . . N TARG S TARG=$$GETPTARG($P(^DD(FILE,FLD,0),"^",2))
 . . Q:TARG=""
 . . N RP S RP=$G(FPIKS(TARG))
 . . Q:RP=""
 . . I RP'=FP S XPAT(FP_"->"_RP)=$G(XPAT(FP_"->"_RP))+1
 W !,"  Cross-PIKS patterns:",!
 N PAT S PAT=""
 F  S PAT=$O(XPAT(PAT)) Q:PAT=""  D
 . W "    ",PAT,$J("",10-$L(PAT)),$J(XPAT(PAT),6)," fields",!
 Q
 ;
LOADPIKS(FPIKS) ;Load PIKS from piks.tsv + piks-triage.tsv
 ; Use ZSYSTEM to read files via shell — avoids YDB device I/O complexity
 N CMD,LINE,IO S IO=$I
 ; Read piks.tsv
 S CMD="cat /home/vehu/export/data-model/piks.tsv | tail -n +2"
 O "pipe":(COMMAND=CMD:READONLY)::"PIPE" U "pipe"
 F  R LINE:5 Q:$T=0  Q:LINE=""  D
 . N FN,PK S FN=$P(LINE,$C(9),1),PK=$P(LINE,$C(9),2)
 . Q:FN=""  Q:PK=""
 . S FPIKS(FN)=PK
 C "pipe" U IO
 ; Read triage supplement
 S CMD="cat /home/vehu/export/data-model/piks-triage.tsv 2>/dev/null | tail -n +2"
 O "pipe2":(COMMAND=CMD:READONLY)::"PIPE" U "pipe2"
 F  R LINE:5 Q:$T=0  Q:LINE=""  D
 . N FN,PK S FN=$P(LINE,$C(9),1),PK=$P(LINE,$C(9),2)
 . Q:FN=""  Q:PK=""
 . S FPIKS(FN)=PK
 C "pipe2" U IO
 Q
 ;
TOPPAR(FILE) ;Walk up to top-level parent
 N PAR S PAR=$G(^DD(FILE,0,"UP"))
 I PAR="" Q FILE
 Q $$TOPPAR(PAR)
 ;
GETTYPE(SPEC) ;Extract human-readable type from DD spec
 I SPEC["P" Q "POINTER"
 I SPEC["V" Q "VARIABLE-POINTER"
 I SPEC["C" Q "COMPUTED"
 I SPEC["D" Q "DATE"
 I SPEC["S" Q "SET"
 I SPEC["N" Q "NUMERIC"
 I SPEC["W" Q "WORD-PROCESSING"
 I SPEC["M" Q "MUMPS"
 I SPEC["F" Q "FREE-TEXT"
 Q "OTHER"
 ;
GETPTARG(TYPE) ;Extract pointer target file# from type spec
 N I,C,NUM,INPTR
 S INPTR=0,NUM=""
 F I=1:1:$L(TYPE) S C=$E(TYPE,I) D  Q:NUM'=""&'INPTR
 . I C="P"!(C="p") S INPTR=1 Q
 . I INPTR,C?1N S NUM=NUM_C Q
 . I INPTR,C'?1N,NUM'="" S INPTR=0 Q
 . I INPTR,C'?1N S INPTR=0,NUM="" Q
 I NUM="" Q ""
 Q +NUM
 ;
UP(S) Q $TR(S,"abcdefghijklmnopqrstuvwxyz","ABCDEFGHIJKLMNOPQRSTUVWXYZ")
 ;
ESC(S) ;Escape tabs/newlines for TSV
 N I,C,OUT S OUT=""
 F I=1:1:$L(S) S C=$E(S,I) D
 . I C=$C(9) S OUT=OUT_" " Q
 . I C=$C(10)!(C=$C(13)) Q
 . S OUT=OUT_C
 Q OUT
