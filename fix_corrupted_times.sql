-- Fix corrupted recurrent_time and time_return in existing offers
-- These values should be the configured arrival/departure times at office (08:00, 18:00)
-- NOT the calculated times with passenger detours (07:53, 18:45)

-- If your configured times are 08:00 arrival and 18:00 departure:
UPDATE carette_db.carpool_offers_recurrent
SET recurrent_time = '08:00:00',
    time_return = '18:00:00'
WHERE status = 'active'
  AND (recurrent_time != '08:00:00' OR time_return != '18:00:00');

-- Verify the update:
SELECT id, driver_name, 
       TIME_FORMAT(recurrent_time, '%H:%i') as arrivee_bureau,
       TIME_FORMAT(time_return, '%H:%i') as depart_bureau
FROM carette_db.carpool_offers_recurrent
WHERE status = 'active';
