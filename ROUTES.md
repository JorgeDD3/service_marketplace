Endpoint                              Methods    Rule                                                             
------------------------------------  ---------  -----------------------------------------------------------------
admin.approve_verification            POST       /admin/verifications/<int:verification_id>/approve               
admin.bookings                        GET        /admin/bookings                                                  
admin.dashboard                       GET        /admin/                                                          
admin.download_verification_doc       GET        /admin/verifications/<int:verification_id>/download/<string:kind>
admin.force_cancel_booking            POST       /admin/bookings/<int:booking_id>/force-cancel                    
admin.reject_verification             POST       /admin/verifications/<int:verification_id>/reject                
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
main.admin_only                       GET        /admin-only                                                      
main.book_service                     POST       /services/<int:service_id>/book                                  
main.cancel_booking                   POST       /my/bookings/<int:booking_id>/cancel                             
main.checkout                         GET, POST  /checkout/<int:booking_id>                                       
main.favicon                          GET        /favicon.ico                                                     
main.home                             GET        /                                                                
main.my_bookings                      GET        /my/bookings                                                     
main.provider_bookings                GET        /provider/bookings                                               
main.service_detail                   GET        /services/<int:service_id>                                       
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
provider.time_off                     GET, POST  /provider/time-off                                               
provider.toggle_availability          POST       /provider/availability/<int:rule_id>/toggle                      
provider.verification                 GET, POST  /provider/verification                                           
provider_services.my_services         GET        /provider/services                                               
provider_services.new_service         GET, POST  /provider/services/new                                           
service_requests.admin_close_request  POST       /admin/requests/<int:request_id>/close                           
service_requests.admin_requests       GET        /admin/requests                                                  
service_requests.claim_request        POST       /provider/requests/<int:request_id>/claim                        
service_requests.close_request        POST       /my/requests/<int:request_id>/close                              
service_requests.fulfill_request      POST       /provider/requests/<int:request_id>/fulfill                      
service_requests.my_requests          GET        /my/requests                                                     
service_requests.provider_requests    GET        /provider/requests                                               
service_requests.request_service      GET, POST  /requests/new                                                    
static                                GET        /static/<path:filename>                                          
