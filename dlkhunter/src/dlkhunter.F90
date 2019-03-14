module dlkhunter_mod
  use iso_c_binding, only : c_int, c_char, C_NULL_CHAR
  implicit none

  interface
    subroutine DLKHunter_init_c(filename, time_profile) bind(C, name="DLKHunter_init")
      use iso_c_binding, only : c_int, c_char
      implicit none
      character(c_char) :: filename
      integer(c_int), value :: time_profile
    end subroutine DLKHunter_init_c

    subroutine DLKHunter_finish_c() bind(C, name="DLKHunter_finish")
    end subroutine DLKHunter_finish_c

    integer function DLKHunter_configureEventGathering_c() bind(C, name="DLKHunter_configureEventGathering")
    end function DLKHunter_configureEventGathering_c

    subroutine DLKHunter_checkpointEventGathering_c(gatherindex, source_name, linenum) &
        bind(C, name="DLKHunter_checkpointEventGathering")
      use iso_c_binding, only : c_int, c_char
      implicit none
      character(c_char) :: source_name
      integer(c_int), value :: gatherindex, linenum
    end subroutine DLKHunter_checkpointEventGathering_c

    subroutine DLKHunter_startEventGathering_c() bind(C, name="DLKHunter_startEventGathering")
    end subroutine DLKHunter_startEventGathering_c

    subroutine DLKHunter_initialiseEventSet_c() bind(C, name="DLKHunter_initialiseEventSet")
    end subroutine DLKHunter_initialiseEventSet_c

    subroutine DLKHunter_displayReport_c(gatherindex) bind(C, name="DLKHunter_displayReport")
      use iso_c_binding, only : c_int
      implicit none
      integer(c_int), value :: gatherindex
    end subroutine DLKHunter_displayReport_c
  end interface

  public DLKHunter_init, DLKHunter_finish, DLKHunter_configureEventGathering, DLKHunter_checkpointEventGathering, &
    DLKHunter_startEventGathering, DLKHunter_initialiseEventSet, DLKHunter_displayReport

contains
  subroutine DLKHunter_init(filename, time_profile)
    character(len=*), intent(in) :: filename
    logical, intent(in) :: time_profile

    character(100) :: string_value
    integer :: str_len, do_time_profile

    string_value=trim(filename)
    string_value=adjustl(string_value)
    str_len=len(trim(filename))+1
    string_value(str_len:str_len)=C_NULL_CHAR

    if (time_profile) then
      do_time_profile=1
    else
      do_time_profile=0
    end if

    call DLKHunter_init_c(string_value, do_time_profile)
  end subroutine DLKHunter_init

  subroutine DLKHunter_finish()
    call DLKHunter_finish_c()
  end subroutine DLKHunter_finish

  integer function DLKHunter_configureEventGathering()
    DLKHunter_configureEventGathering=DLKHunter_configureEventGathering_c()
  end function DLKHunter_configureEventGathering

  subroutine DLKHunter_checkpointEventGathering(gatherindex, source_name, linenum)
    integer, intent(in) :: gatherindex, linenum
    character(len=*), intent(in) :: source_name

    character(100) :: string_value
    integer :: str_len, do_time_profile

    string_value=trim(source_name)
    string_value=adjustl(string_value)
    str_len=len(trim(source_name))+1
    string_value(str_len:str_len)=C_NULL_CHAR

    call DLKHunter_checkpointEventGathering_c(gatherindex, string_value, linenum)
  end subroutine DLKHunter_checkpointEventGathering

  subroutine DLKHunter_startEventGathering()
    call DLKHunter_startEventGathering_c()
  end subroutine DLKHunter_startEventGathering

  subroutine DLKHunter_initialiseEventSet()
    call DLKHunter_initialiseEventSet_c
  end subroutine DLKHunter_initialiseEventSet

  subroutine DLKHunter_displayReport(gatherindex)
    integer, intent(in) :: gatherindex

    call DLKHunter_displayReport_c(gatherindex)
  end subroutine DLKHunter_displayReport
end module dlkhunter_mod
