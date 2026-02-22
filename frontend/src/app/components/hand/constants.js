export const SENSOR_IDS = [
  'palm_center',
  'thumb_tip',
  'thumb_mid',
  'index_tip',
  'index_mid',
  'middle_tip',
  'middle_mid',
  'ring_tip',
  'ring_mid',
  'pinky_tip',
  'pinky_mid',
  'wrist',
];

export const DEFAULT_PRESSURES = SENSOR_IDS.reduce((acc, k) => {
  acc[k] = 0;
  return acc;
}, {});
