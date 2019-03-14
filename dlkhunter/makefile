CC = mpicc
FTN=mpif90

# compiling flags here
CFLAGS   = -fPIC -O3
FFLAGS = -fPIC -O3
LFLAGS   =

# change these to set the proper directories where each files shoould be
SRCDIR   = src
OBJDIR   = build

SOURCES  := $(wildcard $(SRCDIR)/*.c)
INCLUDES := $(wildcard $(SRCDIR)/*.h)
OBJECTS  := $(SOURCES:$(SRCDIR)/%.c=$(OBJDIR)/%.o)
rm       = rm -Rf

cirrus: CFLAGS+= -I /lustre/sw/spack/opt/spack/linux-centos7-x86_64/intel-17.0.2/papi-5.5.0-a26lczvc5iybpvwsuqcdhnt5anmlhmes/include
cirrus: LFLAGS+=-L /lustre/sw/spack/opt/spack/linux-centos7-x86_64/intel-17.0.2/papi-5.5.0-a26lczvc5iybpvwsuqcdhnt5anmlhmes/lib -lpapi
cirrus: dlkhunter

dlkhunter: build_buildDir $(OBJECTS)
	$(CC) -shared -Wl,-soname,libdlkhunter.so -o libdlkhunter.so $(OBJECTS) $(LFLAGS)
	ar rcs libdlkhunter.a $(OBJECTS) $(LFLAGS)

fortran: build_buildDir
	$(FTN) $(FFLAGS)  -o build/fdlkhunter.o -c src/dlkhunter.F90
	$(CC) -shared -Wl,-soname,libfdlkhunter.so -o libfdlkhunter.so build/fdlkhunter.o
	ar rcs libfdlkhunter.a build/fdlkhunter.o

build_buildDir:
	@mkdir -p $(OBJDIR)

$(OBJECTS): $(OBJDIR)/%.o : $(SRCDIR)/%.c
	$(CC) $(CFLAGS) -c $< -o $@

.PHONEY: clean
clean:
	$(rm) $(OBJDIR)	
	$(rm) libdlkhunter.so
