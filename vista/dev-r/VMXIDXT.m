VMXIDXT ;vista-meta — tests for VMXIDX (no M test framework in the image)
 ;;1.0;VISTA-META;;
 ;RUNS IN: container, as vehu:  D EN^VMXIDXT
 ;Writes one line per check and a PASS/FAIL total.
 Q
 ;
EN ;@summary Run every VMXIDX check and print the total
 ;@test LOCS joins XINDEX's chunks; a real routine yields TAG+n;
 ;@test the routine list is the source tree, not File 9.8
 N PASS,FAIL S (PASS,FAIL)=0
 D LOCSUNIT,LOCSREAL,FILESUNIT,LISTREAL
 W !,"VMXIDXT: ",PASS," passed, ",FAIL," failed",!
 Q
 ;
EQ(GOT,WANT,WHAT) ;@summary Record one check as passed or failed
 ;@test helper for the checks below
 I GOT=WANT S PASS=PASS+1 W "  ok   ",WHAT,! Q
 S FAIL=FAIL+1 W "  FAIL ",WHAT,": got """,GOT,""" want """,WANT,"""",!
 Q
 ;
LOCSUNIT ;@summary LOCS joins the chunks of comma-terminated LAB+n text
 ;@test two chunks, one chunk, an absent reference
 K ^UTILITY($J,1,"ZZVMXT")
 S ^UTILITY($J,1,"ZZVMXT","X","DIC ",0)="EN+3,EN+7,"
 S ^UTILITY($J,1,"ZZVMXT","X","DIC ",1)="PROC,"
 S ^UTILITY($J,1,"ZZVMXT","X","XLFDT $$NOW",0)="START+12,"
 D EQ($$LOCS^VMXIDX("ZZVMXT","DIC "),"EN+3,EN+7,PROC","two chunks joined")
 D EQ($$LOCS^VMXIDX("ZZVMXT","XLFDT $$NOW"),"START+12","one location")
 D EQ($$LOCS^VMXIDX("ZZVMXT","NOPE "),"","absent ref")
 K ^UTILITY($J,1,"ZZVMXT")
 Q
 ;
LOCSREAL ;@summary A real routine yields its TAG+n call site
 ;@test PXRMASU calls $$OVERLAP^PXRMINDX at CLASS+16 (source line 20)
 N OK
 K ^UTILITY($J)
 D SETUP^VMXIDX
 S OK=$$PROC^VMXIDX("PXRMASU")
 D EQ(OK,1,"PXRMASU indexed")
 D EQ($$LOCS^VMXIDX("PXRMASU","PXRMINDX $$OVERLAP"),"CLASS+16","real call site")
 K ^UTILITY($J)
 Q
 ;
FILESUNIT ;@summary FILES lists a directory's .m files as routine names
 ;@test _X.m is %X; a non-.m file is not a routine
 N D,L,F,N S D="/tmp/vmxidxt"
 ZSYSTEM "rm -rf "_D_" && mkdir -p "_D
 F F="ZZA.m","_ZZB.m","notes.txt" O D_"/"_F:NEWVERSION U D_"/"_F W " Q",! C D_"/"_F
 D FILES^VMXIDX(D,.L)
 D EQ($D(L("ZZA")),1,"ZZA.m is ZZA")
 D EQ($D(L("%ZZB")),1,"_ZZB.m is %ZZB")
 D EQ($D(L("notes")),0,"notes.txt is not a routine")
 S F="",N=0 F  S F=$O(L(F)) Q:F=""  S N=N+1
 D EQ(N,2,"two routines")
 ZSYSTEM "rm -rf "_D
 Q
 ;
LISTREAL ;@summary ROUTINES lists the image's whole source tree
 ;@test a routine missing from File 9.8 and a %-routine are both listed
 N L,R,N
 D ROUTINES^VMXIDX(.L)
 D EQ($D(L("VADPT6")),1,"VADPT6 (not in File 9.8) listed")
 D EQ($O(^DIC(9.8,"B","VADPT6",0))>0,0,"VADPT6 is indeed absent from File 9.8")
 D EQ($D(L("%ZOSV")),1,"%ZOSV listed")
 S R="",N=0 F  S R=$O(L(R)) Q:R=""  S N=N+1
 D EQ(N>39000,1,"over 39,000 routines listed ("_N_")")
 Q
