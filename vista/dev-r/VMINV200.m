VMINV200 ;Investigate File 200 (NEW PERSON)
 ;
 Q
 ;
RUN ;Show File 200 structure and sample data
 W !,"=== File 200 (NEW PERSON) Investigation ===",!
 W !,"Global: ^VA(200,",!
 W "Total entries: ",$P(^VA(200,0),"^",4),!
 W "Field count: ",$P($G(^DD(200,0)),"^",4),!
 ;
 ; Count entries with key PII fields
 N I,C,WSSN,WDOB,WSEX,WDEA,WNPI,WPROV
 S I=0,C=0,WSSN=0,WDOB=0,WSEX=0,WDEA=0,WNPI=0,WPROV=0
 F  S I=$O(^VA(200,I)) Q:I=""  D
 . S C=C+1
 . I $P($G(^VA(200,I,9)),"^",1)'="" S WSSN=WSSN+1
 . I $P($G(^VA(200,I,5)),"^",1)'="" S WDOB=WDOB+1
 . I $P($G(^VA(200,I,4)),"^",1)'="" S WSEX=WSEX+1
 . I $P($G(^VA(200,I,53.2)),"^",1)'="" S WDEA=WDEA+1
 . I $P($G(^VA(200,I,41.99)),"^",1)'="" S WNPI=WNPI+1
 . I $D(^VA(200,I,53.5)) S WPROV=WPROV+1
 ;
 W !,"Entries walked: ",C,!
 W "  With SSN:            ",WSSN,!
 W "  With DOB:            ",WDOB,!
 W "  With SEX:            ",WSEX,!
 W "  With DEA#:           ",WDEA,!
 W "  With NPI:            ",WNPI,!
 W "  With PROVIDER CLASS: ",WPROV,!
 ;
 ; Sample entries
 W !,"Sample entries (first 10 with SSN):",!
 S I=0,C=0
 F  S I=$O(^VA(200,I)) Q:I=""  Q:C>9  D
 . N SSN S SSN=$P($G(^VA(200,I,9)),"^",1)
 . Q:SSN=""
 . S C=C+1
 . N NAM S NAM=$P($G(^VA(200,I,0)),"^",1)
 . N DOB S DOB=$P($G(^VA(200,I,5)),"^",1)
 . N SEX S SEX=$P($G(^VA(200,I,4)),"^",1)
 . N DEA S DEA=$P($G(^VA(200,I,53.2)),"^",1)
 . N TIT S TIT=$P($G(^VA(200,I,8)),"^",1)
 . W "  ",I,$C(9),NAM
 . W $C(9),"SSN=",SSN
 . W:DOB'="" $C(9),"DOB=",DOB
 . W:SEX'="" $C(9),SEX
 . W:DEA'="" $C(9),"DEA=",DEA
 . I TIT'="" W $C(9),"Title=",$$GETNAME(TIT)
 . W !
 ;
 ; Check: does ^VA(200 contain ANY actual patients (^DPT cross-ref)?
 W !,"=== Patient overlap check ===",!
 W "Does File 200 contain patients from File 2?",!
 N OVERLAP S OVERLAP=0,I=0
 F  S I=$O(^VA(200,I)) Q:I=""  Q:OVERLAP>0  D
 . I $D(^DPT(I)) S OVERLAP=OVERLAP+1
 W "  IEN overlap with ^DPT: ",$S(OVERLAP>0:"YES — shared IEN space!",1:"NO — separate IEN spaces"),!
 ;
 ; Check naming pattern
 W !,"=== Name pattern analysis ===",!
 N PAT S PAT=""
 N PROV,PROG,NURSE,TECH,PHARM,CLRK,OTH
 S PROV=0,PROG=0,NURSE=0,TECH=0,PHARM=0,CLRK=0,OTH=0
 S I=0 F  S I=$O(^VA(200,I)) Q:I=""  D
 . N N S N=$P($G(^VA(200,I,0)),"^",1) Q:N=""
 . I N["PROVIDER" S PROV=PROV+1 Q
 . I N["PROGRAMMER" S PROG=PROG+1 Q
 . I N["NURSE" S NURSE=NURSE+1 Q
 . I N["TECHNICIAN"!(N["TECH,") S TECH=TECH+1 Q
 . I N["PHARMACIST"!(N["PHARM,") S PHARM=PHARM+1 Q
 . I N["CLERK" S CLRK=CLRK+1 Q
 . S OTH=OTH+1
 W "  PROVIDER*:    ",PROV,!
 W "  PROGRAMMER*:  ",PROG,!
 W "  NURSE*:       ",NURSE,!
 W "  TECH*:        ",TECH,!
 W "  PHARMACIST*:  ",PHARM,!
 W "  CLERK*:       ",CLRK,!
 W "  Other:        ",OTH,!
 Q
 ;
GETNAME(IEN) ;Get name from pointer (Title file 3.1)
 I '$D(^DIC(3.1,IEN,0)) Q IEN
 Q $P(^DIC(3.1,IEN,0),"^",1)
