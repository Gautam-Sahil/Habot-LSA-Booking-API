import logging
import requests
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from .models import LSA_Profile, Booking, Payment
from .serializers import LSASerializer, BookingSerializer

logger = logging.getLogger(__name__)

class LSASearchView(generics.ListAPIView):
    serializer_class = LSASerializer

    def get_queryset(self):
        # OPTIMIZATION: prefetch_related completely solves the N+1 problem
        queryset = LSA_Profile.objects.filter(is_active=True).prefetch_related('skills')
        
        skill = self.request.query_params.get('skill', None)
        if skill:
            queryset = queryset.filter(skills__name__icontains=skill)
        return queryset

class BookingCreateView(generics.CreateAPIView):
    serializer_class = BookingSerializer
    
    def perform_create(self, serializer):
        booking = serializer.save()
        
        # MOCK INTEGRATION: Simulating an external payment/verification service
        try:
            logger.info(f"Initiating background verification for booking {booking.id}")
            # We use a very short timeout to ensure the API stays fast
            response = requests.post(
                "https://mock-payment-gateway.habot.io/init", 
                json={"booking_id": str(booking.id)}, 
                timeout=3
            )
        except requests.exceptions.RequestException as e:
            # We log the error but don't crash the booking process
            logger.error(f"External service failed: {e}")

class PaymentWebhookView(APIView):
    """
    Automated webhook endpoint that transitions booking states based on payment success/failure.
    """
    def post(self, request, *args, **kwargs):
        booking_id = request.data.get('booking_id')
        payment_status = request.data.get('status')
        transaction_id = request.data.get('transaction_id')

        try:
            # POKA-YOKE: transaction.atomic ensures if the DB fails halfway, it rolls back
            with transaction.atomic(): 
                # select_for_update() locks the row to prevent race conditions during updates
                booking = Booking.objects.select_for_update().get(id=booking_id)
                
                is_success = (payment_status == 'SUCCESS')
                
                Payment.objects.create(
                    booking=booking,
                    transaction_id=transaction_id,
                    is_successful=is_success
                )

                booking.status = 'CONFIRMED' if is_success else 'FAILED'
                booking.save()

            return Response({"message": "Webhook processed successfully"}, status=status.HTTP_200_OK)

        except Booking.DoesNotExist:
            return Response({"error": "Booking not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)