#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include "papi.h"
#include "dlkhunter.h"

struct event_collection_struct {
  long long * counters, * time_profile_counters;
  char * source_filename;
  int line_num;
  int numberActivations;
};

#define TIME_PROFILE_SLICE 100

static char ** eventIdentifiers=NULL;
static char * reportFilename;
static struct event_collection_struct * collections;
static int totalNumberEvents=0, eventCollectionCounter=0, eventSet=PAPI_NULL, time_profiling;

static void addPAPIEvent(char*);
static void checkStatus(int);
static void dumpTimeCounters(FILE*, int,int);
static void finaliseReports();

void DLKHunter_finish() {
  finaliseReports();
}

void DLKHunter_displayReport(int gatherIndex) {
  int i;
  printf("Reporing performance counters for collection %d with %d activations:\n\n", gatherIndex, collections[gatherIndex].numberActivations);
  for (i=0;i<totalNumberEvents;i++) {
    printf("%s : %lld\n", eventIdentifiers[i], collections[gatherIndex].counters[i]);
  }
  printf("\n");
}

int DLKHunter_configureEventGathering() {
  collections[eventCollectionCounter].counters=(long long *) malloc(sizeof(long long) * totalNumberEvents);
  if (time_profiling) {
    collections[eventCollectionCounter].time_profile_counters=(long long *) malloc(sizeof(long long) * totalNumberEvents * TIME_PROFILE_SLICE);
  } else {
    collections[eventCollectionCounter].time_profile_counters=NULL;
  }
  collections[eventCollectionCounter].numberActivations=0;
  collections[eventCollectionCounter].source_filename=NULL;
  collections[eventCollectionCounter].line_num=0;
  int i;
  for (i=0;i<totalNumberEvents;i++) {
    collections[eventCollectionCounter].counters[i]=0;
  }
  eventCollectionCounter++;
  return eventCollectionCounter-1;
}

void DLKHunter_checkpointEventGathering(int gatheringIndex, char * source_name, int linenum) {
  long long hits[totalNumberEvents];
  if (collections[gatheringIndex].line_num == 0) collections[gatheringIndex].line_num=linenum;
  if (collections[gatheringIndex].source_filename == NULL) {
    collections[gatheringIndex].source_filename=(char*) malloc(sizeof(char) * strlen(source_name) + 1);
    strcpy(collections[gatheringIndex].source_filename, source_name);
  }
  checkStatus(PAPI_stop(eventSet, hits));
  int i;
  for (i=0;i<totalNumberEvents;i++) {
    collections[gatheringIndex].counters[i]+=hits[i];
  }
  if (time_profiling) {
    if (collections[gatheringIndex].numberActivations > 0 && collections[gatheringIndex].numberActivations % TIME_PROFILE_SLICE == 0) {
      FILE * f = fopen(reportFilename, "a");
      dumpTimeCounters(f, gatheringIndex, TIME_PROFILE_SLICE);
      fclose(f);
    }
    int tp_index=collections[gatheringIndex].numberActivations % TIME_PROFILE_SLICE;
    int tp_start=tp_index * totalNumberEvents;
    for (i=0;i<totalNumberEvents;i++) {
      collections[gatheringIndex].time_profile_counters[tp_start+i]=hits[i];
    }
  }
  collections[gatheringIndex].numberActivations++;
}

void DLKHunter_startEventGathering() {
  checkStatus(PAPI_reset(eventSet));
  checkStatus(PAPI_start(eventSet));
}

void DLKHunter_init(char * filename, int time_profile) {
  PAPI_library_init(PAPI_VER_CURRENT);
  PAPI_multiplex_init();
  time_profiling=time_profile;
  reportFilename=(char*) malloc(strlen(filename)+1);
  strcpy(reportFilename, filename);
  FILE * f = fopen(reportFilename, "w");
  time_t timer;
  char buffer[26];
  struct tm* tm_info;

  time(&timer);
  tm_info = localtime(&timer);

  strftime(buffer, 26, "%H:%M:%S %d/%m/%Y", tm_info);
  fprintf(f, "Starting profiling run at %s\n", buffer);
  fclose(f);
}

void DLKHunter_initialiseEventSet() {
  eventIdentifiers=(char**) malloc(sizeof(char*) * 100);
  collections=(struct event_collection_struct *) malloc(sizeof(struct event_collection_struct) * 100);

  checkStatus(PAPI_create_eventset(&eventSet));
  checkStatus(PAPI_assign_eventset_component(eventSet, 0));
  checkStatus(PAPI_set_multiplex(eventSet));

  addPAPIEvent("RESOURCE_STALLS:ALL");
  addPAPIEvent("RESOURCE_STALLS:RS");
  addPAPIEvent("RESOURCE_STALLS:SB");
  addPAPIEvent("RESOURCE_STALLS:ROB");
  addPAPIEvent("IDQ_UOPS_NOT_DELIVERED:CORE");
  addPAPIEvent("BR_INST_RETIRED:ALL_BRANCHES");
  addPAPIEvent("BR_MISP_RETIRED:ALL_BRANCHES");
  addPAPIEvent("LONGEST_LAT_CACHE:REFERENCE");
  addPAPIEvent("LONGEST_LAT_CACHE:MISS");
  addPAPIEvent("CPU_CLK_THREAD_UNHALTED:THREAD_P");
  addPAPIEvent("CPU_CLK_THREAD_UNHALTED:REF_XCLK");
  addPAPIEvent("INST_RETIRED:ANY_P");
  addPAPIEvent("UOPS_EXECUTED_PORT:PORT_0");
  addPAPIEvent("UOPS_EXECUTED_PORT:PORT_1");
  addPAPIEvent("UOPS_EXECUTED_PORT:PORT_2");
  addPAPIEvent("UOPS_EXECUTED_PORT:PORT_3");
  addPAPIEvent("UOPS_EXECUTED_PORT:PORT_4");
  addPAPIEvent("UOPS_EXECUTED_PORT:PORT_5");
  addPAPIEvent("UOPS_EXECUTED_PORT:PORT_6");
  addPAPIEvent("UOPS_EXECUTED_PORT:PORT_7");
  addPAPIEvent("UOPS_ISSUED:ANY");
  addPAPIEvent("CYCLE_ACTIVITY:CYCLES_L2_PENDING");
  addPAPIEvent("CYCLE_ACTIVITY:STALLS_TOTAL");
  addPAPIEvent("CYCLE_ACTIVITY:STALLS_L2_PENDING");
  addPAPIEvent("CYCLE_ACTIVITY:STALLS_LDM_PENDING");
  addPAPIEvent("CYCLE_ACTIVITY:STALLS_L1D_PENDING");
  addPAPIEvent("L1D_PEND_MISS:PENDING_CYCLES");
  addPAPIEvent("L1D_PEND_MISS:FB_FULL");
  addPAPIEvent("L1D:REPLACEMENT");
  addPAPIEvent("IDQ_UOPS_NOT_DELIVERED:CYCLES_LE_1_UOP_DELIV_CORE");
  addPAPIEvent("IDQ_UOPS_NOT_DELIVERED:CYCLES_LE_2_UOP_DELIV_CORE");
  addPAPIEvent("IDQ_UOPS_NOT_DELIVERED:CYCLES_LE_3_UOP_DELIV_CORE");
  addPAPIEvent("IDQ_UOPS_NOT_DELIVERED:CYCLES_FE_WAS_OK");
  addPAPIEvent("UOPS_EXECUTED:STALL_CYCLES");
  addPAPIEvent("UOPS_RETIRED:STALL_CYCLES");
  addPAPIEvent("LOAD_HIT_PRE:SW_PF");
  addPAPIEvent("LOAD_HIT_PRE:HW_PF");
  addPAPIEvent("MEM_UOPS_RETIRED:ALL_LOADS");
  addPAPIEvent("MEM_UOPS_RETIRED:ALL_STORES");
  addPAPIEvent("MEM_LOAD_UOPS_RETIRED:L1_HIT");
  addPAPIEvent("MEM_LOAD_UOPS_RETIRED:L2_HIT");
  addPAPIEvent("MEM_LOAD_UOPS_RETIRED:L3_HIT");
  addPAPIEvent("MEM_LOAD_UOPS_RETIRED:L1_MISS");
  addPAPIEvent("MEM_LOAD_UOPS_RETIRED:L2_MISS");
  addPAPIEvent("MEM_LOAD_UOPS_RETIRED:L3_MISS");
  addPAPIEvent("MEM_LOAD_UOPS_RETIRED:HIT_LFB");
  addPAPIEvent("MEM_LOAD_UOPS_L3_MISS_RETIRED:LOCAL_DRAM");
  addPAPIEvent("DTLB_LOAD_MISSES:MISS_CAUSES_A_WALK");
  addPAPIEvent("DTLB_LOAD_MISSES:STLB_HIT");
  addPAPIEvent("DTLB_STORE_MISSES:MISS_CAUSES_A_WALK");
  addPAPIEvent("DTLB_STORE_MISSES:STLB_HIT");
  addPAPIEvent("PAGE_WALKER_LOADS:DTLB_L1");
  addPAPIEvent("PAGE_WALKER_LOADS:DTLB_L2");
  addPAPIEvent("PAGE_WALKER_LOADS:DTLB_L3");
  addPAPIEvent("PAGE_WALKER_LOADS:DTLB_MEMORY");
}

static void dumpTimeCounters(FILE * f, int eventCollectionCounter, int numberToDump) {
  fprintf(f, "TP: %d %d %d\n", eventCollectionCounter, collections[eventCollectionCounter].numberActivations-numberToDump, numberToDump);
  int i,j, k=0;
  for (i=0;i<numberToDump;i++) {
    for (j=0;j<totalNumberEvents;j++) {
      fprintf(f, "%s%lld", j > 0 ? ",": "", collections[eventCollectionCounter].time_profile_counters[k]);
      k++;
    }
    fprintf(f, "\n");
  }
}

static void finaliseReports() {
  FILE * f = fopen(reportFilename, "a");
  int i, j;
  fprintf(f, "Total number events tracked: %d\n", totalNumberEvents);
  fprintf(f,"-----------------------------\n");
  for (i=0;i<eventCollectionCounter;i++) {
    if (time_profiling) dumpTimeCounters(f, i, collections[i].numberActivations % TIME_PROFILE_SLICE);
    fprintf(f, "Collection: %d\n", i);
    fprintf(f, "Filename: %s\n", collections[i].source_filename != NULL ? collections[i].source_filename : "unknown");
    fprintf(f, "Line number: %d\n", collections[i].line_num);
    fprintf(f, "Activations: %d\n", collections[i].numberActivations);
    for (j=0;j<totalNumberEvents;j++) {
      fprintf(f, "%s = %lld\n", eventIdentifiers[j], collections[i].counters[j]);
    }
    fprintf(f,"-----------------------------\n");
  }
  fclose(f);
}

static void addPAPIEvent(char * eventName){
  int eventCode;
  checkStatus(PAPI_event_name_to_code(eventName, &eventCode));
  checkStatus(PAPI_add_event(eventSet, eventCode));
  eventIdentifiers[totalNumberEvents]=(char*) malloc(sizeof(char) * strlen(eventName) + 1);
  strcpy(eventIdentifiers[totalNumberEvents], eventName);
  totalNumberEvents++;

}

static void checkStatus(int code) {
  if (code != PAPI_OK) {
    printf("Error in PAPI: %s\n", PAPI_strerror(code));
    abort();
  }
}
