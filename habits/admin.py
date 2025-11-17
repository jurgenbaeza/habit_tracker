from django.contrib import admin
from .models import Habit, HabitLog, Tag

class HabitAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'duration', 'created_at')
    filter_horizontal = ('tags',)

admin.site.register(Habit, HabitAdmin)
admin.site.register(HabitLog)
admin.site.register(Tag)
