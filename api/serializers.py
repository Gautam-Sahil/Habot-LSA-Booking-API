from rest_framework import serializers
from .models import Parent, LSA_Profile, Booking, Skill

class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['name']

class LSASerializer(serializers.ModelSerializer):
    skills = SkillSerializer(many=True, read_only=True)

    class Meta:
        model = LSA_Profile
        fields = ['id', 'name', 'skills', 'hourly_rate']

class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ['id', 'parent', 'lsa', 'start_time', 'end_time', 'status']
        read_only_fields = ['status', 'id']

    def validate(self, data):
        lsa = data['lsa']
        start = data['start_time']
        end = data['end_time']

        if start >= end:
            raise serializers.ValidationError("End time must be after start time.")

        # CORE LOGIC: Prevent Overlapping Sessions
        overlapping_bookings = Booking.objects.filter(
            lsa=lsa,
            status__in=['PENDING', 'CONFIRMED'],
            start_time__lt=end,
            end_time__gt=start
        ).exists()

        if overlapping_bookings:
            raise serializers.ValidationError("This LSA is already booked during this exact time slot.")

        return data