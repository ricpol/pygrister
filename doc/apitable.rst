Grist/Pygrister/Gry API list.
=============================

This is a list of all the documented Grist APIs, as they are mapped in 
the Pygrister library and Gry command line tool. 

Service Accounts
----------------

* Grist: ``GET /service-accounts``  

  * Pygrister: ``GristApi.list_service_accounts``  
  
  * Gry: ``gry sacc list``


* Grist: ``POST /service-accounts``  

  * Pygrister: ``GristApi.add_service_account``  
  
  * Gry: ``gry sacc add``


* Grist: ``GET /service-accounts/{saId}``  

  * Pygrister: ``GristApi.see_service_account``  
  
  * Gry: ``gry sacc see``


* Grist: ``PATCH /service-accounts/{saId}``  

  * Pygrister: ``GristApi.update_service_account``  
  
  * Gry: ``gry sacc update``


* Grist: ``DELETE /service-accounts/{saId}``  

  * Pygrister: ``GristApi.delete_service_account``  
  
  * Gry: ``gry sacc delete``


* Grist: ``POST /service-accounts/{saId}/apikey``  

  * Pygrister: ``GristApi.update_service_account_key``  
  
  * Gry: ``gry sacc new-key``


* Grist: ``DELETE /service-accounts/{saId}/apikey``  

  * Pygrister: ``GristApi.delete_service_account_key``  
  
  * Gry: ``gry sacc delete-key``


Users and SCIM
--------------

* Grist: ``GET /scim/v2/Users/{userId}``  

  * Pygrister: ``GristApi.see_user``  
  
  * Gry: ``gry user see``


* Grist: ``GET /scim/v2/Me``  

  * Pygrister: ``GristApi.see_myself``  
  
  * Gry: ``gry user me``


* Grist: ``GET /scim/v2/Users``  

   * Pygrister: ``GristApi.list_users``, ``GristApi.list_users_raw``  
   
   * Gry: ``gry user list``


* Grist: ``POST /scim/v2/Users``  

  * Pygrister: ``GristApi.add_user``  
  
  * Gry: ``gry user new``


* Grist: ``PUT /scim/v2/Users/{userId}``  

  * Pygrister: ``GristApi.update_user_override``  
  
  * Gry: ``NONE``


* Grist: ``PATCH  /scim/v2/Users/{userId}``  

  * Pygrister: ``GristApi.update_user``  
  
  * Gry: ``gry user update``


* Grist: ``DELETE /scim/v2/Users/{userId}``  

  * Pygrister: ``GristApi.delete_user``  
  
  * Gry: ``gry user delete``


* Grist: ``DELETE /users/{userId}``  

  * Pygrister: ``GristApi.delete_myself`` (only as a stub)  
  
  * Gry: *not implemented*


* Grist: ``POST /users/{userId}/enable|disable``
  
  * Pygrister: ``GristApi.enable_user``

  * Gry: ``gry user enable``


* Grist: ``POST   /scim/v2/Users/.search``  

  * Pygrister: ``GristApi.search_users``, ``GristApi.search_users_raw``  
  
  * Gry: *not implemented*


* Grist: ``POST   /scim/v2/Bulk``  

  * Pygrister: ``GristApi.bulk_users``  
  
  * Gry: *not implemented*


* Grist: ``GET /scim/v2/Schemas``  

  * Pygrister: ``GristApi.see_scim_schemas``  
  
  * Gry: ``gry scim schemas``


* Grist: ``GET /scim/v2/ServiceProviderConfig``  

  * Pygrister: ``GristApi.see_scim_config``  
  
  * Gry: ``gry scim config``


* Grist: ``GET /scim/v2/ResourceTypes``  

  * Pygrister: ``GristApi.see_scim_resources`` 
  
  * Gry: ``gry scim resources``


Teams (organisations)
---------------------

* Grist: ``GET /orgs``

  * Pygrister: ``GristApi.list_team_sites``
  
  * Gry: ``gry team list``


* Grist: ``GET /orgs/{orgId}``

  * Pygrister: ``GristApi.see_team``
  
  * Gry: ``gry team see``


* Grist: ``GET /orgs/{orgId}/usage``

  * Pygrister: ``GristApi.see_team_usage``
  
  * Gry: ``gry team usage``


* Grist: ``DELETE /orgs/{orgId}/{name}`` (old: ``DELETE /orgs/{orgId}``)

  * Pygrister: ``GristApi.delete_team`` (old: ``GristApi.delete_team_old``)
  
  * Gry: ``gry team delete``


* Grist: ``PATCH /orgs/{orgId}``

  * Pygrister: ``GristApi.update_team``
  
  * Gry: ``gry team update``


* Grist: ``GET /orgs/{orgId}/access``

  * Pygrister: ``GristApi.list_team_users``
  
  * Gry: ``gry team users``


* Grist: ``PATCH /orgs/{orgId}/access``

  * Pygrister: ``GristApi.update_team_users``
  
  * Gry: ``gry team user-access``


* Grist: ``GET /{orgId}/workspaces``

  * Pygrister: ``GristApi.list_workspaces``
  
  * Gry: ``gry ws list``


* Grist: ``POST /{orgId}/workspaces``

  * Pygrister: ``GristApi.add_workspace``
  
  * Gry: ``gry ws new``


Workspaces
----------

* Grist: ``GET /workspaces/{workspaceId}``

  * Pygrister: ``GristApi.see_workspace ``
  
  * Gry: ``gry ws see``


* Grist: ``PATCH /workspaces/{workspaceId}``

  * Pygrister: ``GristApi.update_workspace``
  
  * Gry: ``gry ws update``


* Grist: ``DELETE /workspaces/{workspaceId}``

  * Pygrister: ``GristApi.delete_workspace``
  
  * Gry: ``gry ws delete``


* Grist: ``POST /workspaces/{workspaceId}/remove|unremove``

  * Pygrister: ``GristApi.trash_workspace``
  
  * Gry: ``gry ws trash``


* Grist: ``GET /workspaces/{workspaceId}/access``

  * Pygrister: ``GristApi.list_workspace_users``
  
  * Gry: ``gry ws users``


* Grist: ``PATCH /workspaces/{workspaceId}/access``

  * Pygrister: ``GristApi.update_workspace_users``
  
  * Gry: ``gry ws user-access``


* Grist: ``POST /workspaces/{workspaceId}/docs``

  * Pygrister: ``GristApi.add_doc``
  
  * Gry: ``gry doc new``


Documents
---------

* Grist: ``GET /docs/{docId}``

  * Pygrister: ``GristApi.see_doc``
  
  * Gry: ``gry doc see``


* Grist: ``PATCH /docs/{docId}``

  * Pygrister: ``GristApi.update_doc``
  
  * Gry: ``gry doc update``


* Grist: ``DELETE /docs/{docId}``

  * Pygrister: ``GristApi.delete_doc``
  
  * Gry: ``gry doc delete``


* Grist: ``POST /docs/{docId}/remove|unremove``

  * Pygrister: ``GristApi.trash_doc``
  
  * Gry: ``gry doc trash``


* Grist: ``PATCH /docs/{docId}/move``

  * Pygrister: ``GristApi.move_doc``
  
  * Gry: ``gry doc move``


* Grist: ``PATCH /docs/{docId}/copy``

  * Pygrister: ``GristApi.copy_doc``
  
  * Gry: ``gry doc copy``


* Grist: ``POST /docs/{docId}/enable|disable``
  
  * Pygrister: ``GristApi.enable_doc``

  * Gry: ``gry doc enable``


* Grist: ``GET /docs/{docId}/access``

  * Pygrister: ``GristApi.list_doc_users``
  
  * Gry: ``gry doc users``


* Grist: ``PATCH /docs/{docId}/access``

  * Pygrister: ``GristApi.update_doc_users``
  
  * Gry: ``gry doc user-access``


* Grist: ``GET /docs/{docId}/download``

  * Pygrister: ``GristApi.download_sqlite``
  
  * Gry: ``gry doc download``


* Grist: ``POST /workspaces/{workspaceId}/import``

  * Pygrister: ``GristApi.upload_sqlite``
  
  * Gry: ``gry doc upload``


* Grist: ``POST /docs/{docId}/states/remove``

  * Pygrister: ``GristApi.delete_doc_history``
  
  * Gry: ``gry doc purge-history``


* Grist: ``POST /docs/{docId}/force-reload``

  * Pygrister: ``GristApi.reload_doc``
  
  * Gry: ``gry doc reload``


* Grist: ``POST /docs/{docId}/recover``

  * Pygrister: ``GristApi.set_recovery_mode``
  
  * Gry: ``gry doc recovery``


Tables
------

* Grist: ``GET /docs/{docId}/tables``

  * Pygrister: ``GristApi.list_tables``
  
  * Gry: ``gry table list``


* Grist: ``POST /docs/{docId}/tables``

  * Pygrister: ``GristApi.add_tables``
  
  * Gry: ``gry table new``


* Grist: ``PATCH /docs/{docId}/tables``

  * Pygrister: ``GristApi.update_tables``
  
  * Gry: ``gry table update``


* Grist: ``GET /docs/{docId}/download/xlsx``

  * Pygrister: ``GristApi.download_excel``
  
  * Gry: ``gry table download -o excel``


* Grist: ``GET /docs/{docId}/download/csv``

  * Pygrister: ``GristApi.download_csv``
  
  * Gry: ``gry table download -o csv``


* Grist: ``GET /docs/{docId}/download/table-schema``

  * Pygrister: ``GristApi.download_schema``
  
  * Gry: ``gry table download -o schema``


Columns
-------

* Grist: ``GET /docs/{docId}/tables/{tableId}/columns``

  * Pygrister: ``GristApi.list_cols``
  
  * Gry: ``gry col list``


* Grist: ``POST /docs/{docId}/tables/{tableId}/columns``

  * Pygrister: ``GristApi.add_cols``
  
  * Gry: ``gry col new``


* Grist: ``PATCH /docs/{docId}/tables/{tableId}/columns``

  * Pygrister: ``GristApi.update_cols``
  
  * Gry: ``gry col update``


* Grist: ``PUT /docs/{docId}/tables/{tableId}/columns``

  * Pygrister: ``GristApi.add_update_cols``
  
  * Gry: *not implemented*


* Grist: ``DELETE /docs/{docId}/tables/{tableId}/columns/{colId}``

  * Pygrister: ``GristApi.delete_column``
  
  * Gry: ``gry col delete``


Records
-------

* Grist: ``GET /docs/{docId}/tables/{tableId}/records``

  * Pygrister: ``GristApi.list_records``
  
  * Gry: ``gry rec list``


* Grist: ``POST /docs/{docId}/tables/{tableId}/records``

  * Pygrister: ``GristApi.add_records``
  
  * Gry: ``gry rec new``


* Grist: ``PATCH /docs/{docId}/tables/{tableId}/records``

  * Pygrister: ``GristApi.update_records``
  
  * Gry: ``gry rec update``


* Grist: ``PUT /docs/{docId}/tables/{tableId}/records``

  * Pygrister: ``GristApi.add_update_records``
  
  * Gry: *not implemented*


* Grist: ``POST /docs/{docId}/tables/{tableId}/data/delete``

  * Pygrister: ``GristApi.delete_rows``
  
  * Gry: ``gry rec delete``


Attachments
-----------

* Grist: ``GET /docs/{docId}/attachments``

  * Pygrister: ``GristApi.list_attachments``
  
  * Gry: ``gry att list``


* Grist: ``POST /docs/{docId}/attachments``

  * Pygrister: ``GristApi.upload_attachments``
  
  * Gry: ``gry att upload``


* Grist: ``GET /docs/{docId}/attachments/{attachmentId}``

  * Pygrister: ``GristApi.see_attachment``
  
  * Gry: ``gry att see``


* Grist: ``GET /docs/{docId}/attachments/{attachmentId}/download``

  * Pygrister: ``GristApi.download_attachment``
  
  * Gry: ``gry att download``


* Grist: ``GET /docs/{docId}/attachments/archive``

  * Pygrister: ``GristApi.download_attachments``
  
  * Gry: ``gry att backup``


* Grist: ``POST /docs/{docId}/attachments/archive``

  * Pygrister: ``GristApi.upload_restore_attachments``
  
  * Gry: ``gry att restore``


* Grist: ``POST /docs/{docId}/attachments/removeUnused``

  * Pygrister: ``GristApi.delete_unused_attachments``
  
  * Gry: ``gry att purge``


* Grist: ``GET /docs/{docId}/attachments/store``

  * Pygrister: ``GristApi.see_attachment_store``
  
  * Gry: ``gry att store``


* Grist: ``POST /docs/{docId}/attachments/store``

  * Pygrister: ``GristApi.update_attachment_store``
  
  * Gry: ``gry att set-store``


* Grist: ``GET /docs/{docId}/attachments/stores``

  * Pygrister: ``GristApi.list_store_settings``
  
  * Gry: ``gry att store-settings``


* Grist: ``POST /docs/{docId}/attachments/transferAll``

  * Pygrister: ``GristApi.transfer_attachments``
  
  * Gry: ``gry att transfer``


* Grist: ``GET /docs/{docId}/attachments/transferStatus``

  * Pygrister: ``GristApi.see_transfer_status``
  
  * Gry: ``gry att transfer-status``


Webhooks
--------

* Grist: ``GET /docs/{docId}/webhooks``

  * Pygrister: ``GristApi.list_webhooks``
  
  * Gry: ``gry hook list``


* Grist: ``POST /docs/{docId}/webhooks``

  * Pygrister: ``GristApi.add_webhooks``
  
  * Gry: ``gry hook new``


* Grist: ``PATCH /docs/{docId}/webhooks/{webhookId}``

  * Pygrister: ``GristApi.update_webhook``
  
  * Gry: ``gry hook update``


* Grist: ``DELETE /docs/{docId}/webhooks/{webhookId}``

  * Pygrister: ``GristApi.delete_webhook``
  
  * Gry: ``gry hook delete``


* Grist: ``DELETE /docs/{docId}/webhooks/queue``

  * Pygrister: ``GristApi.empty_payloads_queue``
  
  * Gry: ``gry hook empty-queue``


Sql
---

* Grist: ``GET /docs/{docId}/sql``

  * Pygrister: ``GristApi.run_sql``
  
  * Gry: ``gry sql``


* Grist: ``POST /docs/{docId}/sql``

  * Pygrister: ``GristApi.run_sql_with_args``
  
  * Gry: ``gry sql --param``

