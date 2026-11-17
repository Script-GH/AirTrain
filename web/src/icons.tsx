type IconProps = { size?: number; className?: string };

const VB = '0 -960 960 960';

function Icon({ d, size = 22, className }: IconProps & { d: string }) {
  return (
    <svg width={size} height={size} viewBox={VB} fill="currentColor" className={className} aria-hidden>
      <path d={d} />
    </svg>
  );
}

const GRID =
  'M200-520q-33 0-56.5-23.5T120-600v-160q0-33 23.5-56.5T200-840h160q33 0 56.5 23.5T440-760v160q0 33-23.5 56.5T360-520H200Zm0 400q-33 0-56.5-23.5T120-200v-160q0-33 23.5-56.5T200-440h160q33 0 56.5 23.5T440-360v160q0 33-23.5 56.5T360-120H200Zm400-400q-33 0-56.5-23.5T520-600v-160q0-33 23.5-56.5T600-840h160q33 0 56.5 23.5T840-760v160q0 33-23.5 56.5T760-520H600Zm0 400q-33 0-56.5-23.5T520-200v-160q0-33 23.5-56.5T600-440h160q33 0 56.5 23.5T840-360v160q0 33-23.5 56.5T760-120H600Z';

const INSIGHTS =
  'M120-160q-33 0-56.5-23.5T40-240q0-33 23.5-56.5T120-320h10.5q4.5 0 9.5 2l182-182q-2-5-2-9.5V-520q0-33 23.5-56.5T400-600q33 0 56.5 23.5T480-520q0 2-2 20l102 102q5-2 9.5-2h21q4.5 0 9.5 2l142-142q-2-5-2-9.5V-560q0-33 23.5-56.5T840-640q33 0 56.5 23.5T920-560q0 33-23.5 56.5T840-480h-10.5q-4.5 0-9.5-2L678-340q2 5 2 9.5v10.5q0 33-23.5 56.5T600-240q-33 0-56.5-23.5T520-320v-10.5q0-4.5 2-9.5L420-442q-5 2-9.5 2H400q-2 0-20-2L198-260q2 5 2 9.5v10.5q0 33-23.5 56.5T120-160Zm40-401-25-54-54-25 54-25 25-54 25 54 54 25-54 25-25 54Zm440-39-38-82-82-38 82-38 38-82 38 82 82 38-82 38-38 82Z';

const HEART =
  'M80-720q0-33 23.5-56.5T160-800h640q33 0 56.5 23.5T880-720v80q0 17-11.5 28.5T840-600q-17 0-28.5-11.5T800-640v-80H160v80q0 17-11.5 28.5T120-600q-17 0-28.5-11.5T80-640v-80Zm80 560q-33 0-56.5-23.5T80-240v-80q0-17 11.5-28.5T120-360q17 0 28.5 11.5T160-320v80h640v-80q0-17 11.5-28.5T840-360q17 0 28.5 11.5T880-320v80q0 33-23.5 56.5T800-160H160Zm261-125.5q10-5.5 15-16.5l124-248 44 88q5 11 15 16.5t21 5.5h200q17 0 28.5-11.5T880-480q0-17-11.5-28.5T840-520H665l-69-138q-5-11-15-15.5t-21-4.5q-11 0-21 4.5T524-658L400-410l-44-88q-5-11-15-16.5t-21-5.5H120q-17 0-28.5 11.5T80-480q0 17 11.5 28.5T120-440h175l69 138q5 11 15 16.5t21 5.5q11 0 21-5.5Z';

const GLOBE =
  'M324-111.5Q251-143 197-197t-85.5-127Q80-397 80-480t31.5-156Q143-709 197-763t127-85.5Q397-880 480-880t156 31.5Q709-817 763-763t85.5 127Q880-563 880-480t-31.5 156Q817-251 763-197t-127 85.5Q563-80 480-80t-156-31.5ZM440-162v-78q-33 0-56.5-23.5T360-320v-40L168-552q-3 18-5.5 36t-2.5 36q0 121 79.5 212T440-162Zm276-102q41-45 62.5-100.5T800-480q0-98-54.5-179T600-776v16q0 33-23.5 56.5T520-680h-80v80q0 17-11.5 28.5T400-560h-80v80h240q17 0 28.5 11.5T600-440v120h40q26 0 47 15.5t29 40.5Z';

const DESKTOP =
  'M400-200v-80H160q-33 0-56.5-23.5T80-360v-400q0-33 23.5-56.5T160-840h640q33 0 56.5 23.5T880-760v400q0 33-23.5 56.5T800-280H560v80h40q17 0 28.5 11.5T640-160q0 17-11.5 28.5T600-120H360q-17 0-28.5-11.5T320-160q0 17 11.5-28.5T360-200h40ZM160-360h640v-400H160v400Z';

const LAPTOP =
  'M80-160q-33 0-56.5-23.5T0-240h160q-33 0-56.5-23.5T80-320v-440q0-33 23.5-56.5T160-840h640q33 0 56.5 23.5T880-760v440q0 33-23.5 56.5T800-240h160q0 33-23.5 56.5T880-160H80Zm428.5-51.5Q520-223 520-240t-11.5-28.5Q497-280 480-280t-28.5 11.5Q440-257 440-240t11.5 28.5Q463-200 480-200t28.5-11.5ZM160-320h640v-440H160v440Z';

const LINK =
  'M680-280h-81q-17 0-28-11.5T560-320q0-17 11.5-28.5T600-360h80v-80q0-17 11.5-28.5T720-480q17 0 28.5 11.5T760-440v80h80q17 0 28.5 11.5T880-320q0 17-11.5 28.5T840-280h-80v80q0 17-11.5 28.5T720-160q-17 0-28.5-11.5T680-200v-80Zm-280 0H280q-83 0-141.5-58.5T80-480q0-83 58.5-141.5T280-680h120q17 0 28.5 11.5T440-640q0 17-11.5 28.5T400-600H280q-50 0-85 35t-35 85q0 50 35 85t85 35h120q17 0 28.5 11.5T440-320q0 17-11.5 28.5T400-280Zm-40-160q-17 0-28.5-11.5T320-480q0-17 11.5-28.5T360-520h240q17 0 28.5 11.5T640-480q0 17-11.5 28.5T600-440H360Zm520-40h-80q0-50-35-85t-85-35H559q-17 0-28-11.5T520-640q0-17 11.5-28.5T560-680h120q83 0 141.5 58.5T880-480Z';

const PAUSE =
  'M600-200q-33 0-56.5-23.5T520-280v-400q0-33 23.5-56.5T600-760h80q33 0 56.5 23.5T760-680v400q0 33-23.5 56.5T680-200h-80Zm-320 0q-33 0-56.5-23.5T200-280v-400q0-33 23.5-56.5T280-760h80q33 0 56.5 23.5T440-680v400q0 33-23.5 56.5T360-200h-80Z';

const PLAY =
  'M320-273v-414q0-17 12-28.5t28-11.5q5 0 10.5 1.5T381-721l326 207q9 6 13.5 15t4.5 19q0 10-4.5 19T707-446L381-239q-5 3-10.5 4.5T360-233q-16 0-28-11.5T320-273Z';

const CLOSE =
  'M480-424 284-228q-11 11-28 11t-28-11q-11-11-11-28t11-28l196-196-196-196q-11-11-11-28t11-28q11-11 28-11t28 11l196 196 196-196q11-11 28-11t28 11q11 11 11 28t-11 28L536-480l196 196q11 11 11 28t-11 28q-11 11-28 11t-28-11L480-424Z';

export function IconGrid({ size = 22, className }: IconProps) {
  return <Icon d={GRID} size={size} className={className} />;
}
export function IconInsights({ size = 22, className }: IconProps) {
  return <Icon d={INSIGHTS} size={size} className={className} />;
}
export function IconHeart({ size = 22, className }: IconProps) {
  return <Icon d={HEART} size={size} className={className} />;
}
export function IconGlobe({ size = 22, className }: IconProps) {
  return <Icon d={GLOBE} size={size} className={className} />;
}
export function IconDesktop({ size = 20, className }: IconProps) {
  return <Icon d={DESKTOP} size={size} className={className} />;
}
export function IconLaptop({ size = 20, className }: IconProps) {
  return <Icon d={LAPTOP} size={size} className={className} />;
}
export function IconLink({ size = 20, className }: IconProps) {
  return <Icon d={LINK} size={size} className={className} />;
}
export function IconPause({ size = 18, className }: IconProps) {
  return <Icon d={PAUSE} size={size} className={className} />;
}
export function IconPlay({ size = 18, className }: IconProps) {
  return <Icon d={PLAY} size={size} className={className} />;
}
export function IconClose({ size = 18, className }: IconProps) {
  return <Icon d={CLOSE} size={size} className={className} />;
}
export function DeviceIconView({ name, size = 20 }: { name: 'desktop' | 'laptop'; size?: number }) {
  return name === 'laptop' ? <IconLaptop size={size} /> : <IconDesktop size={size} />;
}
