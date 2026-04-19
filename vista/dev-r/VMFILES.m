VMFILES ;vista-meta — extract FileMan file inventory to TSV
 ;Spec: docs/vista-meta-spec-v0.4.md § 11.4.1
 ;RUNS IN: container, as vehu
 ;
 ;Walks ^DD and ^DIC to produce a complete file inventory.
 ;Output: TSV to stdout (redirect to files.tsv)
 ;
 ;Usage: D RUN^VMFILES          (writes to /home/vehu/export/normalized/files.tsv)
 ;       D TSV^VMFILES          (TSV to stdout)
 ;       D STATS^VMFILES        (summary stats only)
 ;
 Q
 ;
RUN ;Write files.tsv to normalized directory
 N PATH S PATH="/home/vehu/export/normalized/files.tsv"
 O PATH:NEWVERSION U PATH
 D TSV
 C PATH
 W !,"Written to ",PATH,!
 D STATS
 Q
 ;
TSV ;Output TSV to current device
 ; Header
 W "file_number",$C(9)
 W "file_name",$C(9)
 W "global_root",$C(9)
 W "parent_file",$C(9)
 W "field_count",$C(9)
 W "pointer_in",$C(9)
 W "pointer_out",$C(9)
 W "record_count",$C(9)
 W "is_dinum",$C(9)
 W "piks",$C(9)
 W "piks_method",$C(9)
 W "piks_confidence",$C(9)
 W "piks_evidence",$C(9)
 W "piks_secondary",$C(9)
 W "volatility",$C(9)
 W "sensitivity",$C(9)
 W "portability",$C(9)
 W "volume",$C(9)
 W "subdomain",$C(9)
 W "status",!
 ;
 ; Walk ^DD for every file (numeric entries only)
 N FILE,FNAME,GROOT,PARENT,FCOUNT,PTRIN,PTROUT,RCOUNT,DINUM
 S FILE=""
 F  S FILE=$O(^DD(FILE)) Q:FILE=""  Q:FILE'=+FILE  D
 . ; File name: top-level from ^DIC, subfile from ^DD(FILE,0) piece 1
 . I $D(^DIC(FILE,0)) S FNAME=$P(^DIC(FILE,0),"^",1)
 . E  S FNAME=$P($G(^DD(FILE,0)),"^",1)
 . ;
 . ; Global root from ^DIC if top-level, else from parent
 . S GROOT=$$GETGL(FILE)
 . ;
 . ; Parent file: if file number contains ".", it's a subfile
 . S PARENT=$$GETPAR(FILE)
 . ;
 . ; Field count from ^DD(FILE,0) piece 4, or count fields
 . S FCOUNT=$$FLDCNT(FILE)
 . ;
 . ; Pointer in/out counts
 . S PTRIN=$$PTRIN(FILE)
 . S PTROUT=$$PTROUT(FILE)
 . ;
 . ; Record count (top-level only — subfiles too expensive)
 . S RCOUNT=$$RECCNT(FILE,GROOT)
 . ;
 . ; DINUM check
 . S DINUM=$$ISDINUM(FILE)
 . ;
 . ; Output row — PIKS columns blank (filled by VMPIKS later)
 . W FILE,$C(9)
 . W $$ESC(FNAME),$C(9)
 . W GROOT,$C(9)
 . W PARENT,$C(9)
 . W FCOUNT,$C(9)
 . W PTRIN,$C(9)
 . W PTROUT,$C(9)
 . W RCOUNT,$C(9)
 . W DINUM,$C(9)
 . W $C(9)    ; piks
 . W $C(9)    ; piks_method
 . W $C(9)    ; piks_confidence
 . W $C(9)    ; piks_evidence
 . W $C(9)    ; piks_secondary
 . W $C(9)    ; volatility
 . W $C(9)    ; sensitivity
 . W $C(9)    ; portability
 . W $C(9)    ; volume
 . W $C(9)    ; subdomain
 . W "extracted",!  ; status
 Q
 ;
STATS ;Print summary stats
 N FILE,TOTAL,TOPLEV,SUB,MAXFLD,MAXFILE
 S FILE="",TOTAL=0,TOPLEV=0,SUB=0,MAXFLD=0,MAXFILE=""
 F  S FILE=$O(^DD(FILE)) Q:FILE=""  Q:FILE'=+FILE  D
 . S TOTAL=TOTAL+1
 . I $$GETPAR(FILE)="" S TOPLEV=TOPLEV+1
 . E  S SUB=SUB+1
 . N FC S FC=$$FLDCNT(FILE)
 . I FC>MAXFLD S MAXFLD=FC,MAXFILE=FILE
 W !,"VMFILES Stats:",!
 W "  Total files in ^DD:  ",TOTAL,!
 W "  Top-level files:     ",TOPLEV,!
 W "  Subfiles:            ",SUB,!
 W "  Widest file:         ",MAXFILE," (",MAXFLD," fields)",!
 Q
 ;
 ; === Helper functions ===
 ;
GETGL(FILE) ;Get global root for a file
 ; Top-level: from ^DIC(FILE,0,"GL")
 ; Subfile: inherited from parent
 I $D(^DIC(FILE,0,"GL")) Q ^DIC(FILE,0,"GL")
 ; Try parent
 N PAR S PAR=$$GETPAR(FILE)
 I PAR'="" Q $$GETGL(PAR)
 Q ""
 ;
GETPAR(FILE) ;Get parent file number
 ; ^DD(FILE,0,"UP") points to the parent file
 I $D(^DD(FILE,0,"UP")) Q ^DD(FILE,0,"UP")
 Q ""
 ;
FLDCNT(FILE) ;Count fields in a file
 ; Use ^DD(FILE,0) piece 4 (fast) — maintained by FileMan
 N C S C=+$P($G(^DD(FILE,0)),"^",4)
 Q C
 ;
PTRIN(FILE) ;Count how many OTHER files have pointers TO this file
 ; Check ^DD(FILE,0,"PT") — FileMan maintains this
 N C,X S C=0,X=""
 I '$D(^DD(FILE,0,"PT")) Q 0
 F  S X=$O(^DD(FILE,0,"PT",X)) Q:X=""  S C=C+1
 Q C
 ;
PTROUT(FILE) ;Count pointer fields in this file (pointing OUT)
 N FLD,C,TYPE S FLD="",C=0
 F  S FLD=$O(^DD(FILE,FLD)) Q:FLD=""  Q:FLD'=+FLD  D
 . Q:'$D(^DD(FILE,FLD,0))
 . S TYPE=$P(^DD(FILE,FLD,0),"^",2)
 . ; Pointer types: P (simple), V (variable), Pnn (pointer to file nn)
 . I TYPE["P" S C=C+1
 Q C
 ;
RECCNT(FILE,GROOT) ;Count records (top-level only)
 ; For subfiles, return "" (too expensive to walk nested data)
 I $$GETPAR(FILE)'="" Q ""
 I GROOT="" Q 0
 ; Count first-level subscripts of the global
 N SUB,C S SUB="",C=0
 F  S SUB=$O(@(GROOT_"SUB)")) Q:SUB=""  S C=C+1 Q:C>999999
 Q C
 ;
ISDINUM(FILE) ;Check if file is DINUM (IEN = .01 value)
 ; ^DIC(FILE,0) piece 3 contains flags — "N" in flags = not DINUM
 ; Actually, DINUM is indicated by ^DIC(FILE,0,"GL") containing the file#
 ; Simplest: check if ^DD(FILE,.01,0) piece 2 contains "NJ"
 ; A DINUM file has its .01 set up so IEN matches the value
 I '$D(^DIC(FILE,0)) Q ""
 N FLAGS S FLAGS=$P(^DIC(FILE,0),"^",3)
 I FLAGS["D" Q "Y"
 Q "N"
 ;
ESC(S) ;Escape a string for TSV (replace tabs and newlines)
 N I,C,OUT S OUT=""
 F I=1:1:$L(S) S C=$E(S,I) D
 . I C=$C(9) S OUT=OUT_" " Q  ; tab -> space
 . I C=$C(10) S OUT=OUT_" " Q ; newline -> space
 . I C=$C(13) Q                ; strip CR
 . S OUT=OUT_C
 Q OUT
