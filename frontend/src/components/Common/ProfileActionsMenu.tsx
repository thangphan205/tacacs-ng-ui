import { IconButton } from "@chakra-ui/react"
import { BsThreeDotsVertical } from "react-icons/bs"
import type { ProfilePublic, ProfileScriptPublic } from "@/client"
import useRadiusEnabled from "@/hooks/useRadiusEnabled"
import AddRadiusAttribute from "../Profiles/AddRadiusAttribute"
import DeleteProfile from "../Profiles/DeleteProfile"
import EditProfile from "../Profiles/EditProfile"
import { MenuContent, MenuRoot, MenuTrigger } from "../ui/menu"

interface ProfileActionsMenuProps {
  profile: ProfilePublic
  scriptCount?: number
  scripts?: ProfileScriptPublic[]
}

export const ProfileActionsMenu = ({
  profile,
  scriptCount,
  scripts,
}: ProfileActionsMenuProps) => {
  const radiusEnabled = useRadiusEnabled()
  // A raw-script profile has no structured scripts to add the attribute to.
  const canAddRadius = radiusEnabled && !profile.raw_script && scripts
  return (
    <MenuRoot>
      <MenuTrigger asChild>
        <IconButton variant="ghost" color="inherit">
          <BsThreeDotsVertical />
        </IconButton>
      </MenuTrigger>
      <MenuContent>
        <EditProfile profile={profile} scriptCount={scriptCount} />
        {canAddRadius && (
          <AddRadiusAttribute profile={profile} scripts={scripts} />
        )}
        <DeleteProfile profile={profile} />
      </MenuContent>
    </MenuRoot>
  )
}
