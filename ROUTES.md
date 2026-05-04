Endpoint                              Methods    Rule                                                             
------------------------------------  ---------  -----------------------------------------------------------------
admin.approve_verification            POST       /admin/verifications/<int:verification_id>/approve               
admin.bookings                        GET        /admin/bookings                                                  
admin.dashboard                       GET        /admin/                                                          
admin.decide_refund_request           POST       /admin/refunds/<int:booking_id>/decision                         
admin.download_verification_doc       GET        /admin/verifications/<int:verification_id>/download/<string:kind>
admin.force_cancel_booking            POST       /admin/bookings/<int:booking_id>/force-cancel                    
admin.moderation                      GET        /admin/moderation                                                
admin.refund_requests                 GET        /admin/refunds                                                   
admin.reject_verification             POST       /admin/verifications/<int:verification_id>/reject                
admin.reset_verification              POST       /admin/verifications/<int:verification_id>/reset                 
admin.services                        GET        /admin/services                                                  
admin.toggle_service                  POST       /admin/services/<int:service_id>/toggle                          
admin.toggle_user_active              POST       /admin/users/<int:user_id>/toggle-active                         
admin.users                           GET        /admin/users                                                     
admin.verifications                   GET        /admin/verifications                                             
auth.forgot_password                  GET, POST  /auth/forgot-password                                            
auth.login                            GET, POST  /auth/login                                                      
auth.logout                           GET        /auth/logout                                                     
auth.register                         GET, POST  /auth/register                                                   
auth.reset_password                   GET, POST  /auth/reset-password/<token>                                     
main.book_service                     POST       /services/<int:service_id>/book                                  
main.cancel_booking                   POST       /bookings/<int:booking_id>/cancel                                
main.checkout                         GET, POST  /checkout/<int:booking_id>                                       
main.delete_time_off                  POST       /provider/time-off/<int:time_off_id>/delete                      
main.edit_time_off                    POST       /provider/time-off/<int:time_off_id>/edit                        
main.favicon                          GET        /favicon.ico                                                     
main.health                           GET        /health                                                          
main.home                             GET        /                                                                
main.my_bookings                      GET        /my/bookings                                                     
main.provider_bookings                GET        /provider/bookings                                               
main.provider_delete_service          POST       /provider/services/<int:service_id>/delete                       
main.provider_edit_service            POST       /provider/services/<int:service_id>/edit                         
main.provider_public_profile          GET        /providers/<int:provider_id>                                     
main.provider_time_off                GET        /provider/time-off                                               
main.provider_toggle_service          POST       /provider/services/<int:service_id>/toggle                       
main.request_service                  GET, POST  /requests/new                                                    
main.service_detail                   GET        /services/<int:service_id>                                       
main.service_inquiry                  POST       /services/<int:service_id>/inquiry                               
main.services                         GET        /services                                                        
main.update_booking_status            POST       /provider/bookings/<int:booking_id>/status                       
messages.booking_thread               GET        /messages/booking/<int:booking_id>                               
messages.inbox                        GET        /messages/                                                       
messages.thread                       GET, POST  /messages/<int:conversation_id>                                  
provider.availability                 GET, POST  /provider/availability                                           
provider.availability_preset          POST       /provider/availability/preset                                    
provider.calendar_view                GET        /provider/calendar                                               
provider.dashboard                    GET        /provider/dashboard                                              
provider.delete_availability          POST       /provider/availability/<int:rule_id>/delete                      
provider.profile                      GET, POST  /provider/profile                                                
provider.requests_board               GET        /provider/requests                                               
provider.settings                     GET, POST  /provider/settings                                               
provider.time_off                     GET, POST  /provider/time-off                                               
provider.toggle_availability          POST       /provider/availability/<int:rule_id>/toggle                      
provider.update_availability          POST       /provider/availability/<int:rule_id>/update                      
provider.verification                 GET, POST  /provider/verification                                           
provider_services.my_services         GET        /provider/services                                               
provider_services.new_service         GET, POST  /provider/services/new                                           
service_requests.admin_close_request  POST       /admin/requests/<int:request_id>/close                           
service_requests.admin_requests       GET        /admin/requests                                                  
service_requests.claim_request        POST       /provider/requests/<int:request_id>/claim                        
service_requests.close_request        POST       /my/requests/<int:request_id>/close                              
service_requests.fulfill_request      POST       /provider/requests/<int:request_id>/fulfill                      
service_requests.my_requests          GET        /my/requests                                                     
service_requests.provider_requests    GET        /provider/requests-legacy                                        
service_requests.request_service      GET, POST  /requests/new                                                    
static                                GET        /static/<path:filename>                                          
