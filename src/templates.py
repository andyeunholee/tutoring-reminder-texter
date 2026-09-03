"""English reminder message templates."""

# {program_phrase} is "tutoring ", "College Application ", or "" when one
# merged message spans both programs (note the trailing space in each label).
TEACHER_SINGLE = """\
Hi {recipient_name}, this is a reminder of your {org_name} {program_phrase}session.

Date: {date_long}
Time: {time_range}
Student: {student_names}
Subject: {subject}
{location_line}{meet_line}

Please reply here if anything changes. Thank you!"""

TEACHER_MULTI = """\
Hi {recipient_name}, here is your {org_name} {program_phrase}schedule for {date_long} ({session_count} sessions).

{sessions_block}

Please reply here if anything changes. Thank you!"""

STUDENT_GROUP_SINGLE = """\
Hello! This is a reminder from {org_name} about {recipient_name}'s {program_phrase}session.

Date: {date_long}
Time: {time_range}
Teacher: {teacher_name}
Subject: {subject}
{location_line}{meet_line}

Please let us know if you need to reschedule. Thank you!"""

STUDENT_GROUP_MULTI = """\
Hello! This is a reminder from {org_name} about {recipient_name}'s {program_phrase}sessions on {date_long} ({session_count} sessions).

{sessions_block}

Please let us know if you need to reschedule. Thank you!"""
